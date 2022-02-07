# coding=utf-8
from __future__ import absolute_import
from flask import url_for, jsonify, request, make_response, Response
from werkzeug.exceptions import BadRequest

import octoprint.plugin
from octoprint.util import RepeatedTimer
import pigpio
from .RotaryDecoder import Decoder


class Simplecontrolpanel2Plugin(octoprint.plugin.StartupPlugin,
                                octoprint.plugin.TemplatePlugin,
                                octoprint.plugin.SettingsPlugin,
                                octoprint.plugin.AssetPlugin,
                                octoprint.plugin.BlueprintPlugin
                                ):
    current_brightness = 50
    pi = None
    rotary_decoder = None
    callbacks = []
    lastGpio = 0
    lastTick = 0
    frontEndUpdateTimer = None
    temps = {}
    temp_sensors = []

    def on_after_startup(self):
        self.initialize()
        self.set_brightness()

    def initialize(self):
        self.pi = pigpio.pi()
        self.temp_sensors = []
        self.current_brightness = int(self._settings.get(["default_brightness"]))
        if self._settings.get(["enc_enabled"]):
            self.rotary_decoder = Decoder(self.pi, int(self._settings.get(["enc_a_pin"])),
                                          int(self._settings.get(["enc_b_pin"])),
                                          int(self._settings.get(["enc_sw_pin"])),
                                          self.hw_brightness_control, self.rotary_button_pressed)
        if self._settings.get(["home_enabled"]):
            self.enable_button(int(self._settings.get(["home_x_pin"])))
            self.enable_button(int(self._settings.get(["home_y_pin"])))
            self.enable_button(int(self._settings.get(["home_z_pin"])))

        if self._settings.get(["xy_enabled"]):
            self.enable_button(int(self._settings.get(["x_plus_pin"])))
            self.enable_button(int(self._settings.get(["x_minus_pin"])))
            self.enable_button(int(self._settings.get(["y_plus_pin"])))
            self.enable_button(int(self._settings.get(["y_minus_pin"])))

        if self._settings.get(["z_enabled"]):
            self.enable_button(int(self._settings.get(["z_plus_pin"])))
            self.enable_button(int(self._settings.get(["z_minus_pin"])))

        if self._settings.get(["stop_enabled"]):
            self.enable_button(int(self._settings.get(["stop_pin"])))
        try:
            if self._settings.get(["temp_1_enabled"]):
                self.temp_sensors.append(self.pi.i2c_open(1, 0x44))
            if self._settings.get(["temp_2_enabled"]):
                self.temp_sensors.append(self.pi.i2c_open(1, 0x45))
        except pigpio.error as e:
            self._logger.error("%s. Try restarting the pi", e)

        self.update_temps()
        self.frontEndUpdateTimer = RepeatedTimer(30.0, self.frontend_update)
        self.frontEndUpdateTimer.start()

    def clear_gpio(self):
        self.frontEndUpdateTimer.cancel()
        self.temp_sensors = []
        for sensor in self.temp_sensors:
            self.pi.i2c_close(sensor)
        self.pi.stop()
        if self._settings.get(["enc_enabled"]):
            self.rotary_decoder.cancel()
        for cb in self.callbacks:
            cb.cancel()
        self.callbacks = []

    def enable_button(self, pin):
        self.pi.set_mode(pin, pigpio.INPUT)
        self.pi.set_pull_up_down(pin, pigpio.PUD_DOWN)
        self.pi.set_glitch_filter(pin, 2000)
        self.callbacks.append(self.pi.callback(pin, pigpio.RISING_EDGE, self.button_pressed))

    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self.clear_gpio()
        self.initialize()

    def get_settings_defaults(self):
        return dict(mosfet_enabled=True,
                    mosfet_pin="19",
                    enc_enabled=True,
                    enc_a_pin="26",
                    enc_b_pin="13",
                    enc_sw_pin="6",
                    stop_enabled=True,
                    stop_pin="5",
                    home_enabled=True,
                    home_x_pin="22",
                    home_y_pin="27",
                    home_z_pin="17",
                    xy_enabled=True,
                    x_plus_pin="20",
                    x_minus_pin="24",
                    y_plus_pin="21",
                    y_minus_pin="23",
                    z_enabled=True,
                    z_plus_pin="16",
                    z_minus_pin="18",
                    default_xy_move="10",
                    default_z_move="1",
                    default_brightness="50",
                    temp_1_enabled=False,
                    temp_1_name="E",
                    temp_2_enabled=False,
                    temp_2_name="FB")

    def get_template_configs(self):
        return [
            dict(type="navbar", custom_bindings=True),
            dict(type="settings", custom_bindings=False)
        ]

    def get_assets(self):
        return dict(
            js=["js/SimpleControlPanel.js"],
            css=["css/SimpleControlPanel.css"]
        )

    def hw_brightness_control(self, level):
        self.current_brightness = self.current_brightness + level * 5
        self.set_brightness()

    def rotary_button_pressed(self):
        if self.pi.get_PWM_dutycycle(int(self._settings.get(["mosfet_pin"]))) > 0:
            self.set_pwm(0)
        else:
            self.set_brightness()

    def button_pressed(self, gpio, level, tick):
        self._logger.info('button pressed')
        if tick - self.lastTick > 50000 or gpio != self.lastGpio:
            self.lastGpio = gpio
            self.lastTick = tick

        if gpio == int(self._settings.get(["stop_pin"])):
            self._printer.cancel_print()
        elif gpio == int(self._settings.get(["home_x_pin"])):
            self._printer.home("x")
        elif gpio == int(self._settings.get(["home_y_pin"])):
            self._printer.home("y")
        elif gpio == int(self._settings.get(["home_z_pin"])):
            self._printer.home("z")
        elif gpio == int(self._settings.get(["x_plus_pin"])):
            self.move_tool("X", 1)
        elif gpio == int(self._settings.get(["x_minus_pin"])):
            self.move_tool("X", -1)
        elif gpio == int(self._settings.get(["y_plus_pin"])):
            self.move_tool("Y", 1)
        elif gpio == int(self._settings.get(["y_minus_pin"])):
            self.move_tool("Y", -1)
        elif gpio == int(self._settings.get(["z_plus_pin"])):
            self.move_tool("Z", 1)
        elif gpio == int(self._settings.get(["z_minus_pin"])):
            self.move_tool("Z", -1)

    def move_tool(self, axis, multiplier):
        if axis == "Z":
            move_value = multiplier * int(self._settings.get(["default_z_move"]))
        else:
            move_value = multiplier * int(self._settings.get(["default_xy_move"]))
        self._printer.commands('G91')
        self._printer.commands('G1 %s%s' % (axis, move_value))

    def get_temps(self, h, index):
        try:
            self.pi.i2c_write_byte_data(h, 0x2C, 0x06)
            (b, d) = self.pi.i2c_read_i2c_block_data(h, 0x00, 6)
            temp = -45 + (175 * (d[0] * 256 + d[1]) / 65535.0)
            humidity = 100 * (d[3] * 256 + d[4]) / 65535.0
            return temp, humidity
        except pigpio.error as e:
            self._logger.error("%s failed for sensor %s", e, index)
            return 0, 0

    def update_temps(self):
        for i, sensor in enumerate(self.temp_sensors, start=1):
            temp, hum = self.get_temps(sensor, i)
            if temp != 0 and hum != 0:
                sensor_name = 'temp_{0}'.format(i)
                self.temps[sensor_name] = {'temp': round(temp, 1), 'hum': round(hum, 1)}

    @octoprint.plugin.BlueprintPlugin.route("/update", methods=["GET"])
    def update(self):
        self.update_temps()
        return make_response(jsonify(dict(brightness=self.current_brightness, temps=self.temps)), 200)

    @octoprint.plugin.BlueprintPlugin.route("/values", methods=["GET"])
    def get_values(self):
        return make_response(jsonify(dict(brightness=self.current_brightness, temps=self.temps)), 200)

    @octoprint.plugin.BlueprintPlugin.route("/brightness", methods=["GET"])
    def get_brightness(self):
        return make_response(jsonify({"current_brightness": self.current_brightness}), 200)

    def frontend_update(self):
        self.update_temps()
        self._plugin_manager.send_plugin_message(self._identifier,
                                                 dict(brightness=self.current_brightness, temps=self.temps))

    @octoprint.plugin.BlueprintPlugin.route("/brightness", methods=["PATCH"])
    def sw_brightness_control(self):
        if "application/json" not in request.headers["Content-Type"]:
            return make_response("expected json", 400)
        try:
            data = request.json
        except BadRequest:
            return make_response("malformed request", 400)

        if 'brightness' not in data:
            return make_response("missing duty_cycle attribute", 406)

        if self.current_brightness != int(data['brightness']):
            self.current_brightness = int(data['brightness'])
            self.set_brightness()

        return make_response('', 204)

    def set_brightness(self):
        if self.current_brightness > 100:
            self.current_brightness = 100
        if self.current_brightness < 0:
            self.current_brightness = 0
        self.set_pwm(self.current_brightness)

    def set_pwm(self, value):
        self._logger.info("Setting Mosfet")
        if self._settings.get(["mosfet_enabled"]):
            self.pi.hardware_PWM(int(self._settings.get(["mosfet_pin"])), 800, value * 10000)

    ##~~ Softwareupdate hook

    def get_update_information(self):
        # Define the configuration for your plugin to use with the Software Update
        # Plugin here. See https://docs.octoprint.org/en/master/bundledplugins/softwareupdate.html
        # for details.
        return {
            "SimpleControlPanel2": {
                "displayName": "Simplecontrolpanel2 Plugin",
                "displayVersion": self._plugin_version,

                # version check: github repository
                "type": "github_release",
                "user": "shrikantpatnaik",
                "repo": "OctoPrint-Simplecontrolpanel2",
                "current": self._plugin_version,

                # update method: pip
                "pip": "https://github.com/shrikantpatnaik/OctoPrint-Simplecontrolpanel2/archive/{target_version}.zip",
            }
        }


__plugin_name__ = "SimpleControlPanel2 Plugin"
__plugin_pythoncompat__ = ">=3,<4"  # only python 3


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = Simplecontrolpanel2Plugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }
