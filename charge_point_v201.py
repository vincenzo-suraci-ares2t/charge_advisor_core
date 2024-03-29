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
from ocpp.v201.enums import Action, AttributeType
from ocpp.routing import on

# from .ocpp_central_system.ocpp_central_system.enums import Profiles

# ----------------------------------------------------------------------------------------------------------------------
# Home Assistant packages
# ----------------------------------------------------------------------------------------------------------------------

from homeassistant.components.persistent_notification import DOMAIN as PN_DOMAIN
from homeassistant.const import STATE_OK, STATE_UNAVAILABLE
from homeassistant.helpers import device_registry, entity_component, entity_registry
import homeassistant.helpers.config_validation as cv

# ----------------------------------------------------------------------------------------------------------------------
# Local packages
# ----------------------------------------------------------------------------------------------------------------------

from ocpp_central_system.ComponentsV201.charging_station_2_0_1 import ChargingStationV201
from ocpp_central_system.ComponentsV201.enums_v201 import TierLevel

# ----------------------------------------------------------------------------------------------------------------------
# Local files
# ----------------------------------------------------------------------------------------------------------------------

from .const import *
from .enums import *
from .logger import OcppLog
from .metric import HomeAssistantEntityMetrics
from .evse import HomeAssistantEVSE

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

class HomeAssistantChargePointV201(ChargingStationV201, HomeAssistantEntityMetrics):
    """Home Assistant representation of a Charge Point"""

    def __init__(
            self,
            id: str,
            connection,
            hass,
            config_entry,
            central,
            skip_schema_validation: bool = False,
    ):

        OcppLog.log_i(f"Creazione di una Charging Station che utilizza il protocollo OCPP 2.0.1.")

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

        # Instantiate an OCPP ChargePoint
        ChargingStationV201.__init__(self, id, connection, central, skip_schema_validation)
        HomeAssistantEntityMetrics.__init__(self)

        OcppLog.log_d(f"EVSE ottenuti tramite superclasse: {self._evses}")

        # Impostiamo le metriche
        self.set_metric_value(HAChargePointSensors.identifier.value,f"EVSE: {id}")
        self.set_metric_value(HAChargePointSensors.reconnects.value, 0)

    # overridden
    def _get_init_auth_id_tags(self):
        config = self._hass.data[DOMAIN].get(CONFIG, {})
        return config.get(
            CONF_AUTH_LIST,
            super()._get_init_auth_id_tags()
        )

    # overridden
    async def post_connect(self):

        OcppLog.log_w(f"Lancio post_connect HA.")

        # OcppLog.log_d("Triggering boot notification!!!")
        # await self.trigger_boot_notification()

        # await super().post_connect()

        # await asyncio.sleep(10)

        """Logic to be executed right after a charger connects."""

        # Define custom service handles for charge point
        async def handle_clear_profile(call):
            """Handle the clear profile service call."""
            if self._status == STATE_UNAVAILABLE:
                OcppLog.log_w(f"{self.id} charger is currently unavailable")
                return
            await self.clear_profile()

        async def handle_update_firmware(call):
            """Handle the firmware update service call."""
            if self._status == STATE_UNAVAILABLE:
                OcppLog.log_w(f"{self.id} charger is currently unavailable")
                return
            url = call.data.get("firmware_url")
            delay = int(call.data.get("delay_hours", 0))
            await self.update_firmware(url, delay)

        async def handle_configure(call):
            """Handle the configure service call."""
            if self._status == STATE_UNAVAILABLE:
                OcppLog.log_w(f"{self.id} charger is currently unavailable")
                return
            key = call.data.get("ocpp_key")
            value = call.data.get("value")
            await self.configure(key, value)

        async def handle_get_configuration(call):
            """Handle the get configuration service call."""
            if self._status == STATE_UNAVAILABLE:
                OcppLog.log_w(f"{self.id} charger is currently unavailable")
                return
            key = call.data.get("ocpp_key")
            await self.get_configuration_key(key)

        async def handle_get_diagnostics(call):
            """Handle the get get diagnostics service call."""
            if self._status == STATE_UNAVAILABLE:
                OcppLog.log_w(f"{self.id} charger is currently unavailable")
                return
            url = call.data.get("upload_url")
            await self.get_diagnostics(url)

        async def handle_data_transfer(call):
            """Handle the data transfer service call."""
            if self._status == STATE_UNAVAILABLE:
                OcppLog.log_w(f"{self.id} charger is currently unavailable")
                return
            vendor = call.data.get("vendor_id")
            message = call.data.get("message_id", "")
            data = call.data.get("data", "")
            await self.data_transfer(vendor, message, data)

        self._status = STATE_OK

        try:

            if not self._booting:

                # await ChargingStationV201.post_connect(self)

                OcppLog.log_w(f"Lancio post_connect ORIGINALE.")
                await super().post_connect()
                OcppLog.log_w(f"Post_connect ORIGINALE terminata correttamente.")

                self._booting = True

                self.post_connect_success = False

                # ----------------------------------------------------------------------------------------------------------
                # REGISTRAZIONE DEI SERVIZI SU HOME ASSISTANT
                # ----------------------------------------------------------------------------------------------------------

                """ Register custom services with home assistant """
                self._hass.services.async_register(
                    DOMAIN,
                    HAChargePointServices.service_configure.value,
                    handle_configure,
                    CONF_SERVICE_DATA_SCHEMA,
                )
                self._hass.services.async_register(
                    DOMAIN,
                    HAChargePointServices.service_get_configuration.value,
                    handle_get_configuration,
                    GCONF_SERVICE_DATA_SCHEMA,
                )
                self._hass.services.async_register(
                    DOMAIN,
                    HAChargePointServices.service_data_transfer.value,
                    handle_data_transfer,
                    TRANS_SERVICE_DATA_SCHEMA,
                )

                """if Profiles.SMART in self.attr_supported_features:
                    self._hass.services.async_register(
                        DOMAIN,
                        HAChargePointServices.service_clear_profile.value,
                        handle_clear_profile
                    )

                if Profiles.FW in self.attr_supported_features:
                    self._hass.services.async_register(
                        DOMAIN,
                        HAChargePointServices.service_update_firmware.value,
                        handle_update_firmware,
                        UFW_SERVICE_DATA_SCHEMA,
                    )
                    self._hass.services.async_register(
                        DOMAIN,
                        HAChargePointServices.service_get_diagnostics.value,
                        handle_get_diagnostics,
                        GDIAG_SERVICE_DATA_SCHEMA,
                    )

                    self.post_connect_success = True"""
                self.post_connect_success = True

        except NotImplementedError as e:
            OcppLog.log_e(f"Configuration of the charger failed: {e}")

        OcppLog.log_d(f"Post_connect HA terminata correttamente.")

        self._booting = False

    # ------------------------------------------------------------------------------------------------------------------
    # HOME ASSISTANT METHODS
    # ------------------------------------------------------------------------------------------------------------------

    async def add_new_entities(self):
        await self.add_ha_entities()


    # Updates the Charge Point Home Assistant Entities and
    # its EVSE Home Assistant Entities
    async def update_ha_entities(self):


        while self._adding_entities or self._updating_entities:
            OcppLog.log_d(
                f"{self.id} adding entities: {self._adding_entities} updating entites: {self._updating_entities}. Waiting 1 sec"
            )
            await asyncio.sleep(1)


        self._updating_entities = True

        # Update sensors values in HA
        er = entity_registry.async_get(self._hass)
        dr = device_registry.async_get(self._hass)
        # OcppLog.log_d(f"REGISTRO DISPOSITIVI: {dr.devices}.")
        # OcppLog.log_d(f"Registro entità: {er.entities}.")
        identifiers = {(DOMAIN, self.id)}
        cp_dev = dr.async_get_device(identifiers)
        #OcppLog.log_w(f"Aggiornamento dei Charge Point...")
        #OcppLog.log_w(f"Entità registrate nel Charge Point: {self.ha_entity_unique_ids}.")
        for cp_ent in entity_registry.async_entries_for_device(er, cp_dev.id):
            if cp_ent.unique_id not in self.ha_entity_unique_ids:
                # source: https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/entity_registry.py
                # source: https://dev-docs.home-assistant.io/en/dev/api/helpers.html#module-homeassistant.helpers.entity_registry
                # OcppLog.log_d(f"La entità {cp_ent.unique_id} è registrata in Home Assistant ma non è stata configurata dalla integrazione: verrà eliminata.")
                OcppLog.log_w(f"Entità {cp_ent.unique_id} associata al Charge Point non trovata, rimozione...")
                er.async_remove(
                    entity_id=cp_ent.entity_id
                )
            else:
                await entity_component.async_update_entity(
                    hass=self._hass,
                    entity_id=cp_ent.entity_id
                )
        OcppLog.log_w(f"Charge Point aggiornati.")
        OcppLog.log_w(f"Aggiornamento degli EVSE...")
        OcppLog.log_w(f"EVSE disponibili da aggiornare: {self.evses}.")
        for evse in self._evses:
            #OcppLog.log_w(f"HA-EVSE in esame: {evse}.")
            #OcppLog.log_w(f"Entità registrate nell'EVSE in esame: {evse.ha_entity_unique_ids}.")
            ev_dev = dr.async_get_device({(DOMAIN, evse.identifier)})
            # OcppLog.log_w(f"Device EVSE associato: {ev_dev}.")
            for ev_ent in entity_registry.async_entries_for_device(er, ev_dev.id):
                if ev_ent.unique_id not in evse.ha_entity_unique_ids:
                    er.async_remove(
                        entity_id=ev_ent.entity_id
                    )
                else:
                    await entity_component.async_update_entity(
                        hass=self._hass,
                        entity_id=ev_ent.entity_id
                    )
            #OcppLog.log_w(f"Aggiornamento connettori associati all'EVSE {evse.id}.")
            for conn in evse.connectors:
                await conn.update_ha_entities()
            OcppLog.log_w(f"Connettori aggiornati.")
        OcppLog.log_w(f"EVSE aggiornati.")

        self._updating_entities = False

        OcppLog.log_d(f"Aggiornamento delle entità HA terminato correttamente.")



    async def add_ha_entities(self):
        await self._central.add_ha_entities()

    async def call_ha_service(
            self,
            service_name: str,
            state: bool = True,
            evse_id: int | None = 0,
            connector_id: int = 0,
            transaction_id: int | None = None
    ):
        # Carry out requested service/state change on connected charger.
        resp = False
        match service_name:
            case HAChargePointServices.service_availability.name:
                resp = await self.set_availability(state, int(evse_id), connector_id)
            case HAChargePointServices.service_charge_start.name:
                resp = await self.start_transaction_request(evse_id=1)
            case HAChargePointServices.service_charge_stop.name:
                resp = await self.stop_transaction_request(transaction_id)
            case HAChargePointServices.service_reset.name:
                resp = await self.reset()
            case HAChargePointServices.service_unlock.name:
                resp = await self.unlock(evse_id)
            case HAChargePointServices.service_set_charge_rate:
                resp = await self.set_charge_rate(evse_id = evse_id, limit_amps=0)
            case _:
                OcppLog.log_d(f"{service_name} unknown")
        return resp

    async def async_update_ha_device_info(self, boot_info: dict):

        """Update device info asynchronuously."""
        identifiers = {(DOMAIN, self.id)}

        serial = boot_info.get(OcppMisc.charge_point_serial_number.name, None)
        if serial is not None:
            identifiers.add((DOMAIN, serial))

        dr = device_registry.async_get(self._hass)

        dr.async_get_or_create(
            config_entry_id=self._config_entry.entry_id,
            identifiers=identifiers,
            name=self.id,
            manufacturer=boot_info.get(OcppMisc.charge_point_vendor.name, None),
            model=boot_info.get(OcppMisc.charge_point_model.name, None),
            sw_version=boot_info.get(OcppMisc.charge_point_firmware_version.name, None),
        )

        OcppLog.log_d(f"Info dispositivo {self.id} aggiornate con i dati della BootNotification.")

    # ------------------------------------------------------------------------------------------------------------------
    # Event Loop Tasks
    # ------------------------------------------------------------------------------------------------------------------

    # overridden
    def create_evse_task(self, evse_id: int):
        evse = super().create_evse_task(evse_id)
        OcppLog.log_w(f"EVSE da funzione sovraccaricata generato correttamente.")
        dr = device_registry.async_get(self._hass)
        dr.async_get_or_create(
            config_entry_id=self._config_entry.entry_id,
            identifiers={(DOMAIN, evse.identifier)},
            name=evse.identifier,
            model=self.model + " EVSE",
            via_device=(DOMAIN, self.id),
            manufacturer=self.vendor
        )
        OcppLog.log_w(f"EVSE di nome {evse.identifier} aggiunto correttamente al registro dispositivi.")
        OcppLog.log_w(f"Creazione EVSE integrato...")
        ha_evse = HomeAssistantEVSE(
            id=str(evse_id),
            hass=self._hass,
            config_entry=self._config_entry,
            charge_point=self
        )
        OcppLog.log_w(f"EVSE integrato creato correttamente.")
        return ha_evse

    def create_trigger_status_notification_task(self, evse_id):
        self._hass.async_create_task(
            self.trigger_status_notification(evse_id)
        )

    # overridden
    def create_status_notification_task(self):
        self._hass.async_create_task(
            self.update_ha_entities()
        )

    # overridden
    def create_firmware_status_task(self, msg):
        self._hass.async_create_task(
            self.update_ha_entities()
        )
        self._hass.async_create_task(
            self.notify(msg)
        )

    # overridden
    def create_diagnostics_status_task(self, msg):
        self._hass.async_create_task(
            self.notify(msg)
        )

    # overridden
    def create_security_event_task(self, msg):
        self._hass.async_create_task(
            self.notify(msg)
        )

    # overridden
    def create_boot_notification_task(self, kwargs):
        self._hass.async_create_task(
            self.async_update_ha_device_info(kwargs)
        )
        self._hass.async_create_task(
            self.update_ha_entities()
        )
        super().create_boot_notification_task(kwargs)

    # overridden
    def create_triggered_boot_notification_task(self, msg):
        self._hass.async_create_task(
            self.notify(msg)
        )
        self._hass.async_create_task(
            self.post_connect()
        )

    # overridden
    """def create_remote_start_transaction_task(self):
        self._hass.async_create_task(self.update_ha_entities())

    # overridden
    def create_remote_stop_transaction_task(self):
        self._hass.async_create_task(self.update_ha_entities())"""

    # overridden
    async def force_smart_charging(self):
        return self._config_entry.data.get(
                CONF_FORCE_SMART_CHARGING,
                super().force_smart_charging()
            )

    # overridden
    async def add_evses(self, number_of_evses):
        OcppLog.log_d(f"Aggiunta degli EVSE lato ChargeAdvisor.")
        await super().add_evses(number_of_evses)
        OcppLog.log_d(f"Aggiunta degli EVSE come entità lato integrazione HA.")
        await self.add_ha_entities()

    # overridden
    async def get_evse_instance(self, evse_id):
        return HomeAssistantEVSE(
            self._hass,
            self,
            evse_id
        )

    # overridden
    async def add_evse(self, evse_id):
        OcppLog(f"Versione sovraccaricata di add_evse.")
        dr = device_registry.async_get(self._hass)
        evse = await super().add_evse(evse_id)
        # Create Charge Point's EVSE Devices
        dr.async_get_or_create(
            config_entry_id=self._config_entry.entry_id,
            identifiers={(DOMAIN, evse.identifier)},
            name=evse.identifier,
            model=self.model + " EVSE",
            via_device=(DOMAIN, self.id),
            manufacturer=self.vendor
        )
        OcppLog.log_w(f"EVSE di nome {evse.identifier} aggiunto correttamente al registro dispositivi.")
        OcppLog.log_w(f"Creazione EVSE integrato...")
        ha_evse = HomeAssistantEVSE(
            id=str(evse_id),
            hass=self._hass,
            config_entry=self._config_entry,
            charge_point=self
        )
        OcppLog.log_w(f"EVSE integrato creato correttamente.")

        await self.add_ha_entities()

        return ha_evse

    # overridden
    def get_auth_id_tag(self, id_tag: str):
        auth_id_tag = ChargingStationV201.get_auth_id_tag(self, id_tag)
        auth_id_tag[CONF_NAME] = cv.string
        return auth_id_tag

    # overridden
    async def notify(self, msg: str, params={}):
        await ChargingStationV201.notify(self, msg, params)

        title = params.get("title", "Ocpp integration")

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
    def get_default_authorization_status(self):
        # get the domain wide configuration
        config = self._hass.data[DOMAIN].get(CONFIG, {})
        # get the default authorization status. Use accept if not configured
        return config.get(
            CONF_DEFAULT_AUTH_STATUS,
            super().get_default_authorization_status()
        )

    # overridden
    async def start(self):
        await self.add_ha_entities()
        await super().start()

    # overridden
    async def stop(self):
        self._status = STATE_UNAVAILABLE
        await super().stop()

    # overridden
    async def close_connection(self):
        await super().close_connection()
        await self.update_ha_entities()

    # overridden
    @staticmethod
    def get_default_power_unit():
        return HA_POWER_UNIT

    # overridden
    @staticmethod
    def get_default_energy_unit():
        return HA_ENERGY_UNIT

    # overridden
    async def reconnect(self, connection):
        OcppLog.log_w(f"INIZIO RECONNECT INTEGRATO...")
        # Indichiamo lo stato Home Assistant di nuovo disponibile
        self._status = STATE_OK
        await super().reconnect(connection)
        OcppLog.log_w(f"RECONNECT INTEGRATO CONCLUSO.")

    @on(Action.NotifyReport)
    def on_notify_report(self, request_id, generated_at, tbc, seq_no, report_data, **kwargs):
        res = super().on_notify_report(request_id, generated_at, tbc, seq_no, report_data, **kwargs)
        if not tbc:
            OcppLog.log_e("Invio report concluso, aggiornamento delle entità nell'integrazione...")
            self._hass.async_create_task(self.add_new_entities())
            self._hass.async_create_task(self.update_ha_entities())
            # self._notify_report_ok = True
        return res
