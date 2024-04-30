from eConEXG.triggerBox import lightStimulator
import time

dev = lightStimulator()
dev.vep_mode([1, None, 20, 30, 40, 50])
time.sleep(5)
dev.erp_mode(3)
