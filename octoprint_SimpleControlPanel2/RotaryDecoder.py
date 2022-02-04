import pigpio
import time


class Decoder:
    def __init__(self, pi, gpio_a, gpio_b, gpio_sw, callback, callback_sw):

        self.pi = pi
        self.gpioA = gpio_a
        self.gpioB = gpio_b
        self.callback = callback
        self.callback_sw = callback_sw

        self.levA = 0
        self.levB = 0

        self.lastGpio = None
        self.lastTick = 0
        self.lastTime = 0

        self.pi.set_mode(gpio_a, pigpio.INPUT)
        self.pi.set_mode(gpio_b, pigpio.INPUT)
        self.pi.set_mode(gpio_sw, pigpio.INPUT)

        self.pi.set_pull_up_down(gpio_a, pigpio.PUD_DOWN)
        self.pi.set_pull_up_down(gpio_b, pigpio.PUD_DOWN)
        self.pi.set_pull_up_down(gpio_sw, pigpio.PUD_DOWN)

        self.pi.set_glitch_filter(gpio_sw, 2000)
        self.pi.set_glitch_filter(gpio_a, 2000)
        self.pi.set_glitch_filter(gpio_b, 2000)

        self.cbA = self.pi.callback(gpio_a, pigpio.EITHER_EDGE, self._pulse)
        self.cbB = self.pi.callback(gpio_b, pigpio.EITHER_EDGE, self._pulse)
        self.cbC = self.pi.callback(gpio_sw, pigpio.RISING_EDGE, self._sw_pressed)

    def _pulse(self, gpio, level, tick):
        if gpio == self.gpioA:
            self.levA = level
        else:
            self.levB = level
        if tick - self.lastTick > 5000 or gpio != self.lastGpio:
            self.lastTick = tick
            self.lastGpio = gpio

            if gpio == self.gpioA and level == 1:
                if self.levB == 1:
                    self.callback(-1)
            elif gpio == self.gpioB and level == 1:
                if self.levA == 1:
                    self.callback(1)

    def _sw_pressed(self, gpio, level, tick):
        if tick - self.lastTick > 5000:
            self.lastTick = tick
            self.callback_sw()

    def cancel(self):
        self.cbA.cancel()
        self.cbB.cancel()
        self.cbC.cancel()
