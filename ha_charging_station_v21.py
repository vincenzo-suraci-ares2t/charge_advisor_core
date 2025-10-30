from .ocpp_central_system.ocpp_central_system.ComponentsV21.charging_station_v21 import *
from .ha_charging_station_v201 import HomeAssistantChargingStationV201
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
        # OcppLog.log_d(f"INIZIALIZZAZIONE CLASSE HomeAssistantChargingStationV201 COMPLETATA")
        ChargingStationV21.__init__(
            self,
            id,
            connection,
            central,
            skip_schema_validation
        )
        OcppLog.log_d(f"Creazione di un oggetto di tipo HomeAssistantChargingStationV21 completata.")
