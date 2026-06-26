import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

DOMAIN = "meal_solver_3000"

DEFAULTS = {
    "max_regler":      "köttfärs:2, fisk:1",
    "min_regler":      "vegetarisk:1",
    "ej_konsekutiv":   "potatis, ris, pasta, nudlar",
    "repeat_intervall": 14,
}


def _validate_tagg_regler(value: str) -> str:
    """Validerar format 'tagg:antal, tagg:antal'."""
    if not value.strip():
        return value
    for del_ in value.split(","):
        del_ = del_.strip()
        if not del_:
            continue
        delar = del_.split(":")
        if len(delar) != 2:
            raise vol.Invalid(f"Ogiltigt format '{del_}' — använd tagg:antal")
        try:
            int(delar[1].strip())
        except ValueError:
            raise vol.Invalid(f"'{delar[1].strip()}' är inte ett heltal")
    return value


def _validate_lista(value: str) -> str:
    """Validerar kommaseparerad lista."""
    return value


class MealSolverConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        if user_input is not None:
            return self.async_create_entry(title="Meal Solver 3000", data={})
        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MealSolverOptionsFlow()


class MealSolverOptionsFlow(config_entries.OptionsFlow):

    async def async_step_init(self, user_input=None):
        opts = self.config_entry.options
        errors = {}

        if user_input is not None:
            try:
                _validate_tagg_regler(user_input.get("max_regler", ""))
                _validate_tagg_regler(user_input.get("min_regler", ""))
            except vol.Invalid as e:
                errors["base"] = str(e)
            else:
                return self.async_create_entry(data=user_input)

        schema = vol.Schema({
            vol.Optional("max_regler",
                         default=opts.get("max_regler", DEFAULTS["max_regler"])):
                str,

            vol.Optional("min_regler",
                         default=opts.get("min_regler", DEFAULTS["min_regler"])):
                str,

            vol.Optional("ej_konsekutiv",
                         default=opts.get("ej_konsekutiv", DEFAULTS["ej_konsekutiv"])):
                str,

            vol.Optional("repeat_intervall",
                         default=opts.get("repeat_intervall", DEFAULTS["repeat_intervall"])):
                vol.All(int, vol.Range(min=0, max=365)),
        })

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
