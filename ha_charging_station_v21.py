from .ocpp_central_system.ocpp_central_system.ComponentsV21.charging_station_v21 import *
from .ha_charging_station_v201 import HomeAssistantChargingStationV201
from .ha_evse_v21 import HomeAssistantEVSEV21
from homeassistant.components.persistent_notification import DOMAIN
from homeassistant.helpers import device_registry
from homeassistant.helpers.typing import UNDEFINED
from .logger import OcppLog

class HomeAssistantChargingStationV21(
    HomeAssistantChargingStationV201,
    ChargingStationV21
):
    def __init__(
        self,
        id,
        connection,
        hass,
        config_entry,
        central,
        skip_schema_validation: bool = False
    ):
        # -----------------------------------------------------------------------------------------
        # Superclasses initialization.
        # -----------------------------------------------------------------------------------------
        HomeAssistantChargingStationV201.__init__(
            self,
            id,
            connection,
            hass,
            config_entry,
            central,
            skip_schema_validation
        )
        ChargingStationV21.__init__(
            self,
            id,
            connection,
            central,
            skip_schema_validation
        )

    # ----------------------------------------------------------------------------------------
    # Methods overriding.
    # ----------------------------------------------------------------------------------------
    def create_evse_task(self, evse_id: int):

        #OcppLog.log_d(f"Creating a new OCPP 2.1 EVSE instance...")

        ha_evse = HomeAssistantEVSEV21(
            id=str(evse_id),
            hass=self._hass,
            config_entry=self._config_entry,
            charge_point=self
        )

        return ha_evse

