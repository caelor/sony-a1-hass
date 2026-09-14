from esphome import pins
import esphome.codegen as cg
from esphome.components import esp32
import esphome.config_validation as cv
from esphome.const import CONF_ID, CONF_PIN, CONF_NUMBER
from esphome.types import ConfigType

DEPENDENCIES = ["esp32"]
MULTI_CONF = False
AUTO_LOAD = ["api"]
CODEOWNERS = ["@caelor"]

VARIANTS_NO_RMT = [
    esp32.VARIANT_ESP32C2,
    esp32.VARIANT_ESP32C61,
]

sony_a1_bus_ns = cg.esphome_ns.namespace("sony_a1_bus")
SonyA1Bus = sony_a1_bus_ns.class_("SonyA1Bus", cg.Component)

CONFIG_SCHEMA = cv.All(
    esp32.only_on_variant(
        unsupported=VARIANTS_NO_RMT,
        msg_prefix="Sony A1 bus requires ESP32 RMT",
    ),
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(SonyA1Bus),
            cv.Required(CONF_PIN): cv.int_range(min=0, max=31),
        }
    ).extend(cv.COMPONENT_SCHEMA),
)


async def to_code(config: ConfigType) -> None:
    esp32.include_builtin_idf_component("esp_driver_rmt")
    esp32.add_idf_sdkconfig_option("CONFIG_ESP_TIMER_SUPPORTS_ISR_DISPATCH_METHOD", True)

    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_pin(config[CONF_PIN]))
