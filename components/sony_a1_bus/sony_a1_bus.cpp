#include "sony_a1_bus.h"

#include "esphome/core/application.h"
#include "esphome/core/helpers.h"
#include "esphome/core/log.h"

#include "driver/rmt_rx.h"

#include <cstdio>
#include <cstring>

namespace esphome::sony_a1_bus {

static const char *const TAG = "sony_a1_bus";

SonyA1Bus::~SonyA1Bus() {
  // Clean up heartbeat timer
  if (this->heartbeat_timer_ != nullptr) {
    esp_timer_stop(this->heartbeat_timer_);
    esp_timer_delete(this->heartbeat_timer_);
    this->heartbeat_timer_ = nullptr;
  }
}

void SonyA1Bus::setup() {
  ESP_LOGCONFIG(TAG, "Setting up Sony A1 Bus on GPIO %u...", this->pin_);

  gpio_num_t gpio = gpio_num_t(this->pin_);
  gpio_reset_pin(gpio);
  gpio_set_direction(gpio, GPIO_MODE_INPUT);
  gpio_pullup_en(gpio);

  rmt_rx_channel_config_t rx_chan_cfg;
  memset(&rx_chan_cfg, 0, sizeof(rx_chan_cfg));
  rx_chan_cfg.gpio_num = gpio_num_t(this->pin_);
  rx_chan_cfg.clk_src = RMT_CLK_SRC_DEFAULT;
  rx_chan_cfg.resolution_hz = RMT_RESOLUTION_HZ;
  rx_chan_cfg.mem_block_symbols = RMT_MEM_BLOCK_SYMBOLS;

  esp_err_t err = rmt_new_rx_channel(&rx_chan_cfg, &this->rx_channel_);
  if (err != ESP_OK) {
    ESP_LOGE(TAG, "rmt_new_rx_channel failed: %s", esp_err_to_name(err));
    this->mark_failed();
    return;
  }

  err = rmt_enable(this->rx_channel_);
  if (err != ESP_OK) {
    ESP_LOGE(TAG, "rmt_enable failed: %s", esp_err_to_name(err));
    rmt_del_channel(this->rx_channel_);
    this->rx_channel_ = nullptr;
    this->mark_failed();
    return;
  }

  rmt_rx_event_callbacks_t rx_cbs;
  memset(&rx_cbs, 0, sizeof(rx_cbs));
  rx_cbs.on_recv_done = SonyA1Bus::rmt_rx_done_callback;
  err = rmt_rx_register_event_callbacks(this->rx_channel_, &rx_cbs, this);
  if (err != ESP_OK) {
    ESP_LOGE(TAG, "rmt_rx_register_event_callbacks failed: %s", esp_err_to_name(err));
    rmt_del_channel(this->rx_channel_);
    this->rx_channel_ = nullptr;
    this->mark_failed();
    return;
  }

  memset(&this->rx_config_, 0, sizeof(this->rx_config_));
  this->rx_config_.signal_range_min_ns = RMT_FILTER_US * 1000;
  this->rx_config_.signal_range_max_ns = RMT_IDLE_THRESHOLD_US * 1000;

  err = rmt_receive(this->rx_channel_, this->rx_symbol_buf_,
                    sizeof(this->rx_symbol_buf_), &this->rx_config_);
  if (err != ESP_OK) {
    ESP_LOGE(TAG, "rmt_receive failed: %s", esp_err_to_name(err));
    rmt_del_channel(this->rx_channel_);
    this->rx_channel_ = nullptr;
    this->mark_failed();
    return;
  }
  this->rmt_enabled_ = true;

  esp_timer_create_args_t tx_timer_args = {};
  tx_timer_args.callback = &SonyA1Bus::tx_timer_callback_;
  tx_timer_args.arg = this;
  tx_timer_args.dispatch_method = ESP_TIMER_ISR;
  tx_timer_args.name = "sony-a1-tx";
  err = esp_timer_create(&tx_timer_args, &this->tx_timer_);
  if (err != ESP_OK) {
    ESP_LOGE(TAG, "esp_timer_create (TX) failed: %s", esp_err_to_name(err));
    rmt_disable(this->rx_channel_);
    rmt_del_channel(this->rx_channel_);
    this->rx_channel_ = nullptr;
    this->mark_failed();
    return;
  }

  // Initialize heartbeat timer
  esp_timer_create_args_t heartbeat_timer_args = {};
  heartbeat_timer_args.callback = &SonyA1Bus::heartbeat_timer_callback_;
  heartbeat_timer_args.arg = this;
  heartbeat_timer_args.dispatch_method = ESP_TIMER_TASK;
  heartbeat_timer_args.name = "sony-a1-heartbeat";
  esp_err_t heartbeat_err = esp_timer_create(&heartbeat_timer_args, &this->heartbeat_timer_);
  
  if (heartbeat_err == ESP_OK) {
    // Start periodic heartbeat (60 seconds)
    esp_timer_start_periodic(this->heartbeat_timer_, HEARTBEAT_INTERVAL_MS * 1000);
    ESP_LOGI(TAG, "Heartbeat timer started (interval: %ums)", (unsigned int) HEARTBEAT_INTERVAL_MS);
    
    // Send initial heartbeat
    this->send_heartbeat_();
  } else {
    ESP_LOGE(TAG, "Failed to create heartbeat timer: %d", heartbeat_err);
  }

#ifdef USE_API
  register_service(&SonyA1Bus::on_transmit_service, "transmit",
                   {"data", "max_retries"});

  this->rx_callback_ = [this](const uint8_t *data, size_t len, bool truncated) {
    char hex_buf[format_hex_size(MAX_MSG_LEN)];
    format_hex_to(hex_buf, data, len);

    std::map<std::string, std::string> event_data;
    event_data["data"] = hex_buf;
    event_data["truncated"] = truncated ? "true" : "false";

    this->fire_homeassistant_event("esphome.sony_a1_bus_rx", event_data);

    ESP_LOGD(TAG, "Fired HA event: esphome.sony_a1_bus_rx (data=%s)", hex_buf);
  };
#endif

  ESP_LOGI(TAG, "Sony A1 Bus TX initialized (timer-driven GPIO)");
}

void SonyA1Bus::loop() {
  if (this->bus_state_ == BusState::BUS_TX) {
    if (this->tx_collision_) {
      this->handle_collision_();
    } else if (this->tx_phase_done_) {
      this->handle_tx_complete_();
    }
  }

  if (this->bus_state_ == BusState::BUS_BUSY) {
    uint32_t now = micros();
    if (static_cast<uint32_t>(now - this->last_bus_activity_) >= BUS_IDLE_GUARD_US) {
      this->set_bus_state_(BusState::BUS_IDLE);
      if (this->pending_tx_active_) {
        this->start_tx_attempt_();
      }
    }
  }

  while (this->ring_read_ != this->ring_write_) {
    size_t idx = this->ring_read_ % RING_BUFFER_SIZE;
    const auto &entry = this->ring_buffer_[idx];

    this->decode_rx_symbols_(entry.symbols, entry.num_symbols);

    this->ring_read_++;
  }
}

bool IRAM_ATTR HOT SonyA1Bus::rmt_rx_done_callback(rmt_channel_handle_t channel,
                                                    const rmt_rx_done_event_data_t *edata,
                                                    void *user_data) {
  auto *self = static_cast<SonyA1Bus *>(user_data);

  if (edata == nullptr) {
    return false;
  }

  self->last_bus_activity_ = micros();
  if (self->bus_state_ == BusState::BUS_IDLE) {
    self->bus_state_ = BusState::BUS_BUSY;
  }

  size_t write_idx = self->ring_write_ % RING_BUFFER_SIZE;

  size_t next_write = self->ring_write_ + 1;
  if (next_write % RING_BUFFER_SIZE == self->ring_read_ % RING_BUFFER_SIZE &&
      self->ring_read_ != self->ring_write_) {
    self->stats_.rx_overruns++;
  } else {
    size_t count = edata->num_symbols;
    if (count > RMT_RX_SYMBOL_BUF_LEN) {
      count = RMT_RX_SYMBOL_BUF_LEN;
    }
    memcpy(self->ring_buffer_[write_idx].symbols, edata->received_symbols,
           count * sizeof(rmt_symbol_word_t));
    self->ring_buffer_[write_idx].num_symbols = count;
    self->ring_write_ = next_write;
  }

  esp_err_t err = rmt_receive(channel, self->rx_symbol_buf_, sizeof(self->rx_symbol_buf_), &self->rx_config_);
  if (err != ESP_OK) {
    ESP_LOGW(TAG, "rmt_receive in ISR callback failed: %s", esp_err_to_name(err));
  }

  return false;
}

void SonyA1Bus::set_bus_state_(BusState new_state) {
  if (this->bus_state_ != new_state) {
    BusState old_state = this->bus_state_;
    this->bus_state_ = new_state;
    ESP_LOGD(TAG, "Bus state: %s -> %s",
             LOG_STR_LITERAL(bus_state_to_string(old_state)),
             LOG_STR_LITERAL(bus_state_to_string(new_state)));
  }
}

void SonyA1Bus::decode_rx_symbols_(const rmt_symbol_word_t *symbols, size_t num_symbols) {
  if (num_symbols < 2) {
    this->stats_.rx_decode_errors++;
    ESP_LOGD(TAG, "RX: too few symbols (%u)", (unsigned int) num_symbols);
    return;
  }

  if (symbols[0].level0 != 0 ||
      symbols[0].duration0 < SYNC_LOW_MIN ||
      symbols[0].duration0 > SYNC_LOW_MAX) {
    this->stats_.rx_decode_errors++;
    ESP_LOGD(TAG, "RX: bad sync low duration=%u level=%u",
             (unsigned int) symbols[0].duration0, (unsigned int) symbols[0].level0);
    return;
  }
  if (symbols[0].level1 != 1 ||
      symbols[0].duration1 < SYNC_HIGH_MIN ||
      symbols[0].duration1 > SYNC_HIGH_MAX) {
    this->stats_.rx_decode_errors++;
    ESP_LOGD(TAG, "RX: bad sync high duration=%u level=%u",
             (unsigned int) symbols[0].duration1, (unsigned int) symbols[0].level1);
    return;
  }

  uint8_t rx_buffer[MAX_MSG_LEN] = {0};
  size_t rx_len = 0;
  bool truncated = false;
  size_t bit_index = 0;
  uint8_t current_byte = 0;

  for (size_t i = 1; i < num_symbols; i++) {
    uint32_t low_dur = symbols[i].duration0;
    uint32_t high_dur = symbols[i].duration1;

    if (symbols[i].level0 != 0) {
      this->stats_.rx_decode_errors++;
      ESP_LOGD(TAG, "RX: bit word %u not low-first (level=%u)",
               (unsigned int) i, (unsigned int) symbols[i].level0);
      return;
    }

    int bit;
    if (low_dur >= BIT_0_MIN && low_dur <= BIT_0_MAX) {
      bit = 0;
    } else if (low_dur >= BIT_1_MIN && low_dur <= BIT_1_MAX) {
      bit = 1;
    } else {
      this->stats_.rx_decode_errors++;
      if (low_dur == 0 || low_dur < BIT_0_MIN) {
        ESP_LOGD(TAG, "RX: glitch pulse %uus, aborting",
                 (unsigned int) low_dur);
      } else if (low_dur > BIT_0_MAX && low_dur < BIT_1_MIN) {
        ESP_LOGW(TAG, "RX: ambiguous pulse %uus in guard band, aborting",
                 (unsigned int) low_dur);
      } else {
        ESP_LOGD(TAG, "RX: invalid pulse %uus, aborting",
                 (unsigned int) low_dur);
      }
      return;
    }

    if (i < num_symbols - 1) {
      if (symbols[i].level1 != 1 ||
          high_dur < BIT_DELIM_MIN ||
          high_dur > BIT_DELIM_MAX) {
        this->stats_.rx_decode_errors++;
        ESP_LOGD(TAG, "RX: bad delimiter duration=%uus, aborting",
                 (unsigned int) high_dur);
        return;
      }
    }

    current_byte = (current_byte << 1) | bit;
    bit_index++;

    if (bit_index == 8) {
      if (rx_len < MAX_MSG_LEN) {
        rx_buffer[rx_len++] = current_byte;
      } else {
        truncated = true;
      }
      bit_index = 0;
      current_byte = 0;
    }
  }

  if (bit_index > 0) {
    this->stats_.rx_decode_errors++;
    ESP_LOGD(TAG, "RX: %u trailing bits (partial byte) discarded", (unsigned int) bit_index);
  }

  if (rx_len > 0) {
    this->stats_.rx_messages++;
    char hex_buf[format_hex_pretty_size(MAX_MSG_LEN)];
    format_hex_pretty_to(hex_buf, rx_buffer, rx_len);
    ESP_LOGI(TAG, "RX: decoded %u bytes%s: %s",
             (unsigned int) rx_len, truncated ? " (truncated)" : "", hex_buf);

    if (this->rx_callback_) {
      this->rx_callback_(rx_buffer, rx_len, truncated);
    }
  }
}

bool SonyA1Bus::transmit(const uint8_t *data, size_t len, uint8_t max_retries) {
  if (data == nullptr || len == 0 || len > MAX_MSG_LEN) {
    ESP_LOGW(TAG, "TX rejected: invalid params (len=%u)", (unsigned int) len);
    return false;
  }

  if (this->pending_tx_active_) {
    ESP_LOGW(TAG, "TX rejected: pending slot occupied");
    return false;
  }

  this->stats_.tx_attempts++;

  memcpy(this->pending_tx_data_, data, len);
  this->pending_tx_len_ = len;
  this->pending_tx_retries_ = max_retries;
  this->pending_tx_active_ = true;

  if (this->bus_state_ == BusState::BUS_IDLE) {
    this->start_tx_attempt_();
  }

  return true;
}

#ifdef USE_API
void SonyA1Bus::on_transmit_service(std::vector<int32_t> data, int32_t max_retries) {
  if (data.empty() || data.size() > MAX_MSG_LEN) {
    this->stats_.tx_rejections++;
    ESP_LOGW(TAG, "TX rejected: invalid data length (%u)", (unsigned int) data.size());
    return;
  }

  uint8_t tx_buffer[MAX_MSG_LEN];
  for (size_t i = 0; i < data.size(); i++) {
    if (data[i] < 0 || data[i] > 255) {
      this->stats_.tx_rejections++;
      ESP_LOGW(TAG, "TX rejected: byte %u out of range (%ld)", (unsigned int) i, (long) data[i]);
      return;
    }
    tx_buffer[i] = static_cast<uint8_t>(data[i]);
  }

  uint8_t retries = (max_retries > 0 && max_retries <= 255) ? static_cast<uint8_t>(max_retries) : 0;

  if (!this->transmit(tx_buffer, data.size(), retries)) {
    this->stats_.tx_rejections++;
    ESP_LOGW(TAG, "TX rejected: bus busy or pending slot occupied");
  }
}
#endif

void SonyA1Bus::start_tx_attempt_() {
  this->tx_bit_index_ = 0;
  this->tx_current_byte_ = this->pending_tx_data_[0];
  this->tx_collision_ = false;
  this->tx_phase_done_ = false;

  esp_timer_stop(this->tx_timer_);
  this->set_bus_state_(BusState::BUS_TX);
  this->tx_phase_ = TxPhase::TX_PHASE_SYNC_LOW;
  SonyA1Bus::drive_low_(gpio_num_t(this->pin_));
  esp_timer_start_once(this->tx_timer_, TX_SYNC_LOW_US);
}

void SonyA1Bus::handle_collision_() {
  esp_timer_stop(this->tx_timer_);
  SonyA1Bus::release_bus_(gpio_num_t(this->pin_));
  this->set_bus_state_(BusState::BUS_BUSY);
  this->last_bus_activity_ = micros();

  this->tx_byte_index_ = 0;
  this->tx_bit_index_ = 0;
  this->tx_current_byte_ = 0;
  this->tx_phase_ = TxPhase::TX_PHASE_SYNC_LOW;

  if (this->pending_tx_retries_ > 0) {
    this->pending_tx_retries_--;
    ESP_LOGW(TAG, "collision: retrying (%u remaining)", this->pending_tx_retries_);
  } else {
    ESP_LOGW(TAG, "collision: retries exhausted");
    this->pending_tx_active_ = false;
    this->stats_.tx_rejections++;
  }
}

void SonyA1Bus::handle_tx_complete_() {
  esp_timer_stop(this->tx_timer_);
  SonyA1Bus::release_bus_(gpio_num_t(this->pin_));
  this->set_bus_state_(BusState::BUS_IDLE);
  this->pending_tx_active_ = false;
  this->stats_.tx_successes++;
  
  char hex_buf[format_hex_pretty_size(MAX_MSG_LEN)];
  format_hex_pretty_to(hex_buf, this->pending_tx_data_, this->pending_tx_len_);
  ESP_LOGI(TAG, "TX succeeded (%u bytes): %s",
           (unsigned int) this->pending_tx_len_, hex_buf);
}

void IRAM_ATTR SonyA1Bus::advance_tx_gpio_() {
  if (this->tx_collision_) {
    return;
  }

  gpio_num_t gpio = gpio_num_t(this->pin_);

  switch (this->tx_phase_) {
    case TxPhase::TX_PHASE_SYNC_LOW:
      SonyA1Bus::release_bus_(gpio);
      esp_timer_start_once(this->tx_timer_, TX_SYNC_HIGH_US);
      this->tx_phase_ = TxPhase::TX_PHASE_SYNC_HIGH;
      break;

    case TxPhase::TX_PHASE_SYNC_HIGH:
      this->tx_byte_index_ = 0;
      this->tx_current_byte_ = this->pending_tx_data_[0];
      this->tx_bit_index_ = 0;
      SonyA1Bus::drive_low_(gpio);
      esp_timer_start_once(this->tx_timer_,
                           (this->tx_current_byte_ & 0x80) ? TX_BIT_1_LOW_US : TX_BIT_0_LOW_US);
      this->tx_phase_ = TxPhase::TX_PHASE_BIT_LOW;
      break;

    case TxPhase::TX_PHASE_BIT_LOW:
      SonyA1Bus::release_bus_(gpio);
      esp_timer_start_once(this->tx_timer_, TX_BIT_DELIM_US);
      this->tx_phase_ = TxPhase::TX_PHASE_BIT_HIGH;
      break;

    case TxPhase::TX_PHASE_BIT_HIGH:
      this->tx_bit_index_++;
      if (this->tx_bit_index_ >= 8) {
        this->tx_bit_index_ = 0;
        this->tx_byte_index_++;
        if (this->tx_byte_index_ >= this->pending_tx_len_) {
          SonyA1Bus::release_bus_(gpio);
          esp_timer_start_once(this->tx_timer_, TX_INTER_MESSAGE_US);
          this->tx_phase_ = TxPhase::TX_PHASE_INTER_MESSAGE;
          this->tx_phase_done_ = true;
          return;
        }
        this->tx_current_byte_ = this->pending_tx_data_[this->tx_byte_index_];
      }
      SonyA1Bus::drive_low_(gpio);
      esp_timer_start_once(this->tx_timer_,
                           (this->tx_current_byte_ & (0x80 >> this->tx_bit_index_)) ? TX_BIT_1_LOW_US : TX_BIT_0_LOW_US);
      this->tx_phase_ = TxPhase::TX_PHASE_BIT_LOW;
      break;

    case TxPhase::TX_PHASE_INTER_MESSAGE:
      this->tx_phase_done_ = true;
      break;
  }
}

void IRAM_ATTR SonyA1Bus::tx_timer_callback_(void *arg) {
  auto *self = static_cast<SonyA1Bus *>(arg);

  if (self->tx_phase_ == TxPhase::TX_PHASE_SYNC_HIGH ||
      self->tx_phase_ == TxPhase::TX_PHASE_BIT_HIGH) {
    uint32_t gpio_level = (GPIO.in >> self->pin_) & 1;
    if (gpio_level == 0) {
      self->tx_collision_ = true;
      return;
    }
  }

  self->advance_tx_gpio_();
}

void SonyA1Bus::heartbeat_timer_callback_(void *arg) {
  auto *self = static_cast<SonyA1Bus *>(arg);
  self->send_heartbeat_();
}

void SonyA1Bus::send_heartbeat_() {
#ifdef USE_API
  std::map<std::string, std::string> event_data;
  event_data["bridge_version"] = BRIDGE_VERSION;
  
  this->fire_homeassistant_event("esphome.sony_a1_bus_heartbeat", event_data);
  
  ESP_LOGD(TAG, "Fired heartbeat event: version=%s", BRIDGE_VERSION);
#endif
}

void SonyA1Bus::dump_config() {
  ESP_LOGCONFIG(TAG, "Sony A1 Bus");
  ESP_LOGCONFIG(TAG, "  Pin: %u", this->pin_);
  ESP_LOGCONFIG(TAG, "  RMT Resolution: %u Hz", (unsigned int) RMT_RESOLUTION_HZ);
  ESP_LOGCONFIG(TAG, "  RMT Idle Threshold: %u us", (unsigned int) RMT_IDLE_THRESHOLD_US);
  ESP_LOGCONFIG(TAG, "  RMT Filter: %u us", (unsigned int) RMT_FILTER_US);
  ESP_LOGCONFIG(TAG, "  Max Message Length: %u bytes", (unsigned int) MAX_MSG_LEN);
  BusState state = this->bus_state_;
  ESP_LOGCONFIG(TAG, "  Bus State: %s", LOG_STR_LITERAL(bus_state_to_string(state)));

  ESP_LOGCONFIG(TAG, "  Statistics:");
  ESP_LOGCONFIG(TAG, "    RX Messages: %u", (unsigned int) this->stats_.rx_messages);
  ESP_LOGCONFIG(TAG, "    RX Overruns: %u", (unsigned int) this->stats_.rx_overruns);
  ESP_LOGCONFIG(TAG, "    RX Decode Errors: %u", (unsigned int) this->stats_.rx_decode_errors);
  ESP_LOGCONFIG(TAG, "    TX Attempts: %u", (unsigned int) this->stats_.tx_attempts);
  ESP_LOGCONFIG(TAG, "    TX Successes: %u", (unsigned int) this->stats_.tx_successes);
  ESP_LOGCONFIG(TAG, "    TX Rejections: %u", (unsigned int) this->stats_.tx_rejections);
}

}  // namespace esphome::sony_a1_bus
