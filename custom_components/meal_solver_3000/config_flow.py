import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

DOMAIN = "meal_solver_3000"

WEEKDAYS = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]

DEFAULTS = {
    "max_rules":        "köttfärs:2, fisk:1",
    "min_rules":        "vegetarisk:1",
    "no_consecutive":   "potatis, ris, pasta, nudlar",
    "repeat_interval":  14,
    "language":         "sv",
    "auto_shuffle":     True,
    "shuffle_weekday":  "sunday",
    "shuffle_time":     "17:00",
}


def _validate_tag_rules(value: str) -> str:
    """Validates format 'tag:count, tag:count'."""
    if not value.strip():
        return value
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        parts = part.split(":")
        if len(parts) != 2:
            raise vol.Invalid(f"Invalid format '{part}' — use tag:count")
        try:
            int(parts[1].strip())
        except ValueError:
            raise vol.Invalid(f"'{parts[1].strip()}' is not an integer")
    return value


def _validate_list(value: str) -> str:
    """Validates a comma-separated list."""
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
                _validate_tag_rules(user_input.get("max_rules", ""))
                _validate_tag_rules(user_input.get("min_rules", ""))
            except vol.Invalid as e:
                errors["base"] = str(e)
            else:
                return self.async_create_entry(data=user_input)

        schema = vol.Schema({
            vol.Optional("max_rules",
                         default=opts.get("max_rules", DEFAULTS["max_rules"])):
                str,

            vol.Optional("min_rules",
                         default=opts.get("min_rules", DEFAULTS["min_rules"])):
                str,

            vol.Optional("no_consecutive",
                         default=opts.get("no_consecutive", DEFAULTS["no_consecutive"])):
                str,

            vol.Optional("repeat_interval",
                         default=opts.get("repeat_interval", DEFAULTS["repeat_interval"])):
                vol.All(int, vol.Range(min=0, max=365)),

            vol.Optional("language",
                         default=opts.get("language", DEFAULTS["language"])):
                vol.In(["sv", "en"]),

            vol.Optional("auto_shuffle",
                         default=opts.get("auto_shuffle", DEFAULTS["auto_shuffle"])):
                bool,

            vol.Optional("shuffle_weekday",
                         default=opts.get("shuffle_weekday", DEFAULTS["shuffle_weekday"])):
                vol.In(WEEKDAYS),

            vol.Optional("shuffle_time",
                         default=opts.get("shuffle_time", DEFAULTS["shuffle_time"])):
                str,
        })

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
