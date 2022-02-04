$(function() {
    function SimpleControlPanelViewModel(parameters) {
        var self = this;
        self.pluginName = "SimpleControlPanel";
        self.temperatureModel = parameters[0];
        self.settings = parameters[1];

        self.currentBrightness = ko.observable();
        self.temps = ko.observable();
        self.tempString = ko.observable();
        self.tempString("Loading...");

        self.currentBrightness.subscribe(function(newValue) {
            $.ajax({
                type: "PATCH",
                contentType: "application/json",
                data: JSON.stringify({
                    brightness: newValue
                }),
                url: self.buildPluginUrl('/brightness'),
                error: function (error) {
                    console.log(error)
                }
            })
        });

        self.temps.subscribe(function(newValue) {
            var string = "";
            if(self.temperatureModel.hasBed()) {
                string += "B:" + self.temperatureModel.bedTemp.actual()+ "°C";
                string +=" |";
            }
            if(self.temperatureModel.hasTools()) {
                string +=" ";
                string += "T:" + self.temperatureModel.tools()[0].actual()+ "°C";
                string +=" ";
            }
            if(self.settings.settings.plugins.SimpleControlPanel.temp_1_enabled()) {
                string +="| ";
                if(newValue.temp_1) {
                    if(newValue.temp_1.temp) {
                        string += self.settings.settings.plugins.SimpleControlPanel.temp_1_name() + ":" + newValue.temp_1.temp + "°C";
                        string +=" ";
                    }
                    if(newValue.temp_1.hum) {
                        string += newValue.temp_1.hum + "%";
                        string +=" ";
                    }
                }
            }

            if(self.settings.settings.plugins.SimpleControlPanel.temp_2_enabled()) {
                string +="| ";
                if(newValue.temp_2) {
                    if(newValue.temp_2.temp) {
                        string += self.settings.settings.plugins.SimpleControlPanel.temp_2_name() + ":" + newValue.temp_2.temp + "°C";
                        string +=" ";
                    }
                    if(newValue.temp_2.hum) {
                        string += newValue.temp_2.hum + "%";
                        string +=" ";
                    }
                }
            }
            self.tempString(string)
        });

        self.buildPluginUrl = function (path) {
            return window.PLUGIN_BASEURL + self.pluginName + path;
        };

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if(plugin != "SimpleControlPanel") {
                return
            }
            self.currentBrightness(data.brightness);
            self.temps(data.temps);
        };

        self.onBeforeBinding = function() {
            $.ajax({
                type: "GET",
                dataType: "json",
                contentType: "application/json",
                url: self.buildPluginUrl('/values'),
                success: function(data) {
                    self.currentBrightness(data.brightness);
                    self.temps(data.temps);
                }
            })

        };
    }

    // This is how our plugin registers itself with the application, by adding some configuration
    // information to the global variable OCTOPRINT_VIEWMODELS
    OCTOPRINT_VIEWMODELS.push([
        // This is the constructor to call for instantiating the plugin
        SimpleControlPanelViewModel,

        // This is a list of dependencies to inject into the plugin, the order which you request
        // here is the order in which the dependencies will be injected into your view model upon
        // instantiation via the parameters argument
        ["temperatureViewModel", "settingsViewModel"],

        // Finally, this is the list of selectors for all elements we want this view model to be bound to.
        ["#navbar_plugin_SimpleControlPanel"]
    ]);
});
