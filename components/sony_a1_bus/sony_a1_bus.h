#pragma once

#include "esphome/core/component.h"
#include "driver/rmt_rx.h"

#ifdef USE_API
#include "esphome/components/api/custom_api_device.h"
#endif

#include <driver/gpio.h>
#include <esp_timer.h>
#include <soc/gpio_struct.h>

#include <functional>

namespace esphome::sony_a1_bus {

inline constexpr uint32_t RMT_RESOLUTION_HZ = 1000000;
inline constexpr uint32_t RMT_IDLE_THRESHOLD_US = 2700;
inline constexpr uint32_t RMT_FILTER_US = 2;
inline constexpr size_t RMT_MEM_BLOCK_SYMBOLS = 480;
inline constexpr size_t RMT_RX_SYMBOL_BUF_LEN = 480;
inline constexpr size_t RING_BUFFER_SIZE = 3;

inline constexpr uint32_t SYNC_LOW_MIN = 1700;
inline constexpr uint32_t SYNC_LOW_MAX = 3100;
inline constexpr uint32_t SYNC_HIGH_MIN = 400;
inline constexpr uint32_t SYNC_HIGH_MAX = 800;
inline constexpr uint32_t BIT_0_MIN = 310;
inline constexpr uint32_t BIT_0_MAX = 810;
inline constexpr uint32_t BIT_1_MIN = 950;
inline constexpr uint32_t BIT_1_MAX = 1450;
inline constexpr uint32_t BIT_DELIM_MIN = 400;
inline constexpr uint32_t BIT_DELIM_MAX = 800;

inline constexpr size_t MAX_MSG_LEN = 32;

inline constexpr uint32_t BUS_IDLE_GUARD_US = 10000;

inline constexpr uint32_t TX_SYNC_LOW_US = 2410;
inline constexpr uint32_t TX_SYNC_HIGH_US = 600;
inline constexpr uint32_t TX_BIT_0_LOW_US = 570;
inline constexpr uint32_t TX_BIT_1_LOW_US = 1210;
inline constexpr uint32_t TX_BIT_DELIM_US = 600;
inline constexpr uint32_t TX_INTER_MESSAGE_US = 3000;

enum class BusState : uint8_t {
  BUS_IDLE = 0,
  BUS_BUSY = 1,
  BUS_TX = 2,
};

enum class TxPhase : uint8_t {
  TX_PHASE_SYNC_LOW = 0,
  TX_PHASE_SYNC_HIGH,
  TX_PHASE_BIT_LOW,
  TX_PHASE_BIT_HIGH,
  TX_PHASE_INTER_MESSAGE,
};

inline const char *bus_state_to_string(BusState state) {
  switch (state) {
    case BusState::BUS_IDLE:
      return "IDLE";
    case BusState::BUS_BUSY:
      return "BUSY";
    case BusState::BUS_TX:
      return "TX";
    default:
      return "?";
  }
}

using rx_callback_t = std::function<void(const uint8_t *data, size_t len, bool truncated)>;

class SonyA1Bus final : public Component
#ifdef USE_API
    ,
     public api::CustomAPIDevice
#endif
{
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;
  ~SonyA1Bus();

  void set_pin(uint8_t pin) { this->pin_ = pin; }

  float get_setup_priority() const override { return setup_priority::BUS; }

  bool transmit(const uint8_t *data, size_t len, uint8_t max_retries);

#ifdef USE_API
  void on_transmit_service(std::vector<int32_t> data, int32_t max_retries);
#endif

 protected:
  struct RingBufferEntry {
    rmt_symbol_word_t symbols[RMT_RX_SYMBOL_BUF_LEN];
    size_t num_symbols;
  };

  struct Stats {
    uint32_t rx_messages{0};
    uint32_t rx_decode_errors{0};
    uint32_t tx_attempts{0};
    uint32_t tx_successes{0};
    uint32_t tx_rejections{0};
    volatile uint32_t rx_overruns{0};
  };
  Stats stats_{};

  uint8_t pin_{0};
  rmt_channel_handle_t rx_channel_{nullptr};
  rmt_symbol_word_t rx_symbol_buf_[RMT_RX_SYMBOL_BUF_LEN];
  rmt_receive_config_t rx_config_{};
  RingBufferEntry ring_buffer_[RING_BUFFER_SIZE];
  volatile size_t ring_write_{0};
  volatile size_t ring_read_{0};
  bool rmt_enabled_{false};

  esp_timer_handle_t tx_timer_{nullptr};
  esp_timer_handle_t heartbeat_timer_{nullptr};

  static constexpr const char* BRIDGE_VERSION = "1.0.0";
  static constexpr uint32_t HEARTBEAT_INTERVAL_MS = 5000;  // 5 seconds

  void send_heartbeat_();
  static void heartbeat_timer_callback_(void *arg);

  volatile BusState bus_state_{BusState::BUS_IDLE};
  volatile uint32_t last_bus_activity_{0};

  volatile TxPhase tx_phase_{TxPhase::TX_PHASE_SYNC_LOW};
  volatile bool tx_collision_{false};
  volatile bool tx_phase_done_{false};
  size_t tx_byte_index_{0};
  uint8_t tx_current_byte_{0};
  uint8_t tx_bit_index_{0};

  uint8_t pending_tx_data_[MAX_MSG_LEN];
  size_t pending_tx_len_{0};
  uint8_t pending_tx_retries_{0};
  bool pending_tx_active_{false};

  rx_callback_t rx_callback_;

  void decode_rx_symbols_(const rmt_symbol_word_t *symbols, size_t num_symbols);
  void set_bus_state_(BusState new_state);


  static inline void IRAM_ATTR drive_low_(gpio_num_t gpio) {
    GPIO.out_w1tc = (1ULL << gpio);
    GPIO.enable_w1ts = (1ULL << gpio);
  }

  static inline void IRAM_ATTR release_bus_(gpio_num_t gpio) {
    GPIO.enable_w1tc = (1ULL << gpio);
  }

  void start_tx_attempt_();
  void handle_collision_();
  void handle_tx_complete_();
  void advance_tx_gpio_();

  static void tx_timer_callback_(void *arg);

  static bool IRAM_ATTR HOT rmt_rx_done_callback(rmt_channel_handle_t channel,
                                                  const rmt_rx_done_event_data_t *edata,
                                                  void *user_data);
};

}  // namespace esphome::sony_a1_bus
