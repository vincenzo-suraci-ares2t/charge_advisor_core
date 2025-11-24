from .ha_connector_v201 import HomeAssistantConnectorV201
from .ocpp_central_system.ocpp_central_system.ComponentsV21.connector_v21 import ConnectorV21
from .logger import OcppLog

class HomeAssistantConnectorV21(ConnectorV21, HomeAssistantConnectorV201):
    def __init__(
        self,
        hass,
        config_entry,
        evse,
        connector_id = 0
    ):
        # ----------------------------------------------------------------------------------------
        # Superclasses initialization.
        # ----------------------------------------------------------------------------------------
        ConnectorV21.__init__(
            self=self,
            evse=evse, 
            connector_id=connector_id
        )
        HomeAssistantConnectorV201.__init__(
            self=self,
            hass=hass, 
            config_entry=config_entry, 
            evse=evse, 
            connector_id=connector_id
        )
        OcppLog.log_d(f"OCPP 2.1 HOME ASSISTANT CONNECTOR INITIALIZED")