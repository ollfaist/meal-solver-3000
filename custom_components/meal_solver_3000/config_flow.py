import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

DOMAIN = "meal_solver_3000"

DEFAULTS = {
    "max_kottfars":    2,
    "max_fisk":        1,
    "min_vegetarisk":  1,
    "repeat_intervall": 14,
}


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
        return MealSolverOptionsFlow(config_entry)


class MealSolverOptionsFlow(config_entries.OptionsFlow):

    async def async_step_init(self, user_input=None):
        opts = self.config_entry.options

        if user_input is not None:
            return self.async_create_entry(data=user_input)

        schema = vol.Schema({
            vol.Optional("max_kottfars",
                         default=opts.get("max_kottfars", DEFAULTS["max_kottfars"])):
                vol.All(int, vol.Range(min=1, max=7)),

            vol.Optional("max_fisk",
                         default=opts.get("max_fisk", DEFAULTS["max_fisk"])):
                vol.All(int, vol.Range(min=0, max=7)),

            vol.Optional("min_vegetarisk",
                         default=opts.get("min_vegetarisk", DEFAULTS["min_vegetarisk"])):
                vol.All(int, vol.Range(min=0, max=7)),

            vol.Optional("repeat_intervall",
                         default=opts.get("repeat_intervall", DEFAULTS["repeat_intervall"])):
                vol.All(int, vol.Range(min=0, max=365)),
        })

        return self.async_show_form(step_id="init", data_schema=schema)
