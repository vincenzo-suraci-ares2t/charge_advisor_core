"""Representation of a OCCP Entities."""

# ----------------------------------------------------------------------------------------------------------------------
# Python packages
# ----------------------------------------------------------------------------------------------------------------------

from __future__ import annotations
import asyncio

# ----------------------------------------------------------------------------------------------------------------------
# External packages
# ----------------------------------------------------------------------------------------------------------------------

# pip install voluptuous
import voluptuous as vol

from ocpp.exceptions import NotImplementedError

# ----------------------------------------------------------------------------------------------------------------------
# Home Assistant packages
# ----------------------------------------------------------------------------------------------------------------------

from homeassistant.components.persistent_notification import DOMAIN as PN_DOMAIN
from homeassistant.const import STATE_OK, STATE_UNAVAILABLE, UnitOfTime
from homeassistant.helpers import device_registry, entity_component, entity_registry
from homeassistant.helpers.typing import UNDEFINED
import homeassistant.helpers.config_validation as cv

# ----------------------------------------------------------------------------------------------------------------------
# Local packages
# ----------------------------------------------------------------------------------------------------------------------

from ocpp_central_system.ComponentsV201.charging_station_v201 import ChargingStationV201
from ocpp_central_system.ComponentsV201.evse_v201 import EVSEV201

# ----------------------------------------------------------------------------------------------------------------------
# Local files
# ----------------------------------------------------------------------------------------------------------------------

from .const import *
from .enums import *
from .logger import OcppLog
from .ha_metric import HomeAssistantEntityMetrics
from .ha_connector_v201 import HomeAssistantConnectorV201

# ----------------------------------------------------------------------------------------------------------------------
# Home Assistant Voluptuous SCHEMAS
# ----------------------------------------------------------------------------------------------------------------------

UFW_SERVICE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("firmware_url"): cv.string,
        vol.Optional("delay_hours"): cv.positive_int,
    }
)

CONF_SERVICE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("ocpp_key"): cv.string,
        vol.Required("value"): cv.string,
    }
)

GCONF_SERVICE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("ocpp_key"): cv.string,
    }
)

GDIAG_SERVICE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("upload_url"): cv.string,
    }
)

TRANS_SERVICE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("vendor_id"): cv.string,
        vol.Optional("message_id"): cv.string,
        vol.Optional("data"): cv.string,
    }
)

class HomeAssistantEVSEV201(
    EVSEV201,
    HomeAssistantEntityMetrics
):
    """Home Assistant representation of a Charge Point"""

    def __init__(
        self,
        id: str,
        hass,
        config_entry,
        charge_point
    ):

        # --------------------------------------------------------------------------------------------------------------
        # Variabili Home Assistant
        # --------------------------------------------------------------------------------------------------------------

        # Oggetto Home Assistant
        self._hass = hass

        # Oggetto Config Entry
        self._config_entry = config_entry

        # Stato (di Home Assistant) del Charge Point
        self._status = STATE_OK

        # Flag per tenere conto se il Charge Point sta aggiungendo le proprie entità
        self._adding_entities = False

        # Flag per tenere conto se il Charge Point sta aggiornando le proprie entità
        self._updating_entities = False

        # Lista di entità Home Assistant registrate in fase di setup
        self.ha_entity_unique_ids: list[str] = []

        # Istanziare la superclasse e le metriche.
        EVSEV201.__init__(self, charge_point, id)
        HomeAssistantEntityMetrics.__init__(self)

        # Impostiamo le metriche
        self.set_metric_value(HAEVSESensors.identifier.value, id)


    # ------------------------------------------------------------------------------------------------------------------
    # HOME ASSISTANT METHODS
    # ------------------------------------------------------------------------------------------------------------------

    # Updates the Charge Point Home Assistant Entities and
    # its Connectors Home Assistant Entities
    async def update_ha_entities(self):

        while self._adding_entities or self._updating_entities:
            msg = f"EVSE {self.identifier} is already "
            if self._adding_entities:
                msg += "adding"
            elif self._updating_entities:
                msg += "updating"
            msg += f" its own Home Assistant entities > Waiting {HA_UPDATE_ENTITIES_WAITING_SECS} sec"
            OcppLog.log_w(msg)
            await asyncio.sleep(HA_UPDATE_ENTITIES_WAITING_SECS)

        self._updating_entities = True

        OcppLog.log_d(f"L'EVSE {self.identifier} ha INIZIATO l'aggiornamento le entità Home Assistant")

        # Update sensors values in HA
        er = entity_registry.async_get(self._hass)
        dr = device_registry.async_get(self._hass)
        identifiers = {(DOMAIN, self.identifier)}
        #OcppLog.log_d(f"Identificatori EVSE: {identifiers}.")
        evse_dev = dr.async_get_device(identifiers)
        #OcppLog.log_w(f"Entità registrate nell'EVSE: {self.ha_entity_unique_ids}.")
        for evse_ent in entity_registry.async_entries_for_device(er, evse_dev.id):
            OcppLog.log_d(f"Entità EVSE in esame: {evse_ent}")
            if evse_ent.unique_id not in self.ha_entity_unique_ids:
                # source: https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/entity_registry.py
                # source: https://dev-docs.home-assistant.io/en/dev/api/helpers.html#module-homeassistant.helpers.entity_registry
                # OcppLog.log_d(f"La entità {cp_ent.unique_id} è registrata in Home Assistant ma non è stata configurata dalla integrazione: verrà eliminata.")
                er.async_remove(evse_ent.entity_id)
                #OcppLog.log_w(f"Entità associata all'EVSE non trovata, rimozione...")
            else:
                await entity_component.async_update_entity(self._hass, evse_ent.entity_id)

        self._updating_entities = False

        OcppLog.log_d(f"L'EVSE {self.identifier} ha TERMINATO l'aggiornamento le entità Home Assistant")

        for conn in self._connectors:
            #OcppLog.log_w(f"Tipo di connettore associato all'EVSE: {type(conn)}.")
            await conn.update_ha_entities()

    # ------------------------------------------------------------------------------------------------------------------
    # Event Loop Tasks
    # ------------------------------------------------------------------------------------------------------------------

    # overridden
    async def add_connectors(self, number_of_connectors):
        await super().add_connectors(number_of_connectors)
        await self.add_ha_entities()

    # overridden
    async def get_connector_instance(self, connector_id):
        return HomeAssistantConnectorV201(
            hass=self._hass,
            config_entry=self._config_entry,
            evse=self,
            connector_id=connector_id
        )

    # overridden
    async def add_connector(self, connector_id = None):
        # Creazione del dispositivo connettore.
        await super().add_connector(connector_id)
        ha_conn = self.get_connector_by_id(connector_id)
        dr = device_registry.async_get(self._hass)
        model = UNDEFINED
        if self.charging_station.model is not None:
            model = self.charging_station.model + " Connector"
        dr.async_get_or_create(
            config_entry_id=self._config_entry.entry_id,
            identifiers={(DOMAIN, ha_conn.identifier)},
            name=ha_conn.identifier,
            model=model,
            via_device=(DOMAIN, self.identifier),
            manufacturer=self.charging_station.vendor
        )

    # overridden
    async def notify(self, msg: str, params={}):
        await ChargingStationV201.notify(self, msg, params)
        title = params.get("title", HA_NOTIFY_TITLE)
        """Notify user via HA web frontend."""
        await self._hass.services.async_call(
            PN_DOMAIN,
            "create",
            service_data={
                "title": title,
                "message": msg,
            },
            blocking=False,
        )
        return True

    # overridden
    @staticmethod
    def get_default_power_unit():
        return HA_POWER_UNIT

    # overridden
    @staticmethod
    def get_default_energy_unit():
        return HA_ENERGY_UNIT

    # overridden
    def get_default_session_time_uom(self):
        return UnitOfTime.MINUTES

    # overridden
    def is_available_for_reservation(self):
        OcppLog.log_w(f"Home Assistant EVSE is available: {self.is_available()}.")
        return super().is_available_for_reservation() and self.is_available()

    # overridden
    def is_available_for_charging(self):
        return super().is_available_for_charging() and self.is_available()

    # overridden
    def is_available(self):
        return super().is_available() and self.charge_point.is_available()

    ####################################################################################################################
    # Metodo per gestire le istruzioni ricevute dall'interfaccia grafica.
    async def call_ha_service(
            self,
            service_name: str,
            state: bool = True,
            connector_id: int = None
    ):
        return await self._charge_point.call_ha_service(
            service_name=service_name,
            state=state,
            evse_id=self.id,
            connector_id=connector_id,
            transaction_id=self._active_transaction_id
        )
    ####################################################################################################################