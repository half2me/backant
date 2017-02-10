from Adafruit_MotorHAT import Adafruit_MotorHAT, Adafruit_StepperMotor

class motor():
    def __init__(self):
        self.mh = Adafruit_MotorHAT()
        self.stepper = self.mh.getStepper(200, 1)  # 200 steps/rev, motor port #1
        self.stepper.setSpeed(30)
        self.state = True

    def release(self):
        self.mh.getMotor(1).run(Adafruit_MotorHAT.RELEASE)
        self.mh.getMotor(2).run(Adafruit_MotorHAT.RELEASE)
        self.mh.getMotor(3).run(Adafruit_MotorHAT.RELEASE)
        self.mh.getMotor(4).run(Adafruit_MotorHAT.RELEASE)

    def low(self):
        if not self.state:
            self.stepper.step(100, Adafruit_MotorHAT.FORWARD, Adafruit_MotorHAT.DOUBLE)
            self.release()
            self.state = True

    def high(self):
        if self.state:
            self.stepper.step(100, Adafruit_MotorHAT.BACKWARD, Adafruit_MotorHAT.DOUBLE)
            self.release()
            self.state = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.high()