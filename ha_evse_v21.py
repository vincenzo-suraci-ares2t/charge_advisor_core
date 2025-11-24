from .ha_evse import HomeAssistantEVSEV201
from .ha_connector_v21 import HomeAssistantConnectorV21
from .ocpp_central_system.ocpp_central_system.ComponentsV21.evse_v21 import EVSEV21
from .logger import OcppLog

class HomeAssistantEVSEV21(
    HomeAssistantEVSEV201,
    EVSEV21
):
    def __init__(
        self,
        id: str,
        hass,
        config_entry,
        charge_point
    ):
        
        # ----------------------------------------------------------------------------------------
        # Superclasses initialization.
        # ----------------------------------------------------------------------------------------
        HomeAssistantEVSEV201.__init__(
            self=self,
            id=id, 
            hass=hass, 
            config_entry=config_entry,
            charge_point=charge_point
        )
        EVSEV21.__init__(
            self=self,
            charge_point=charge_point,
            evse_id=id
        )

    # ----------------------------------------------------------------------------------------
    # Overriding methods.
    # ----------------------------------------------------------------------------------------
    async def get_connector_instance(self, connector_id):
        return HomeAssistantConnectorV21(
            hass=self._hass,
            config_entry=self._config_entry,
            evse=self,
            connector_id=connector_id
        )