from eConEXG.triggerBox import lightStimulator

if __name__ == "__main__":
    dev = lightStimulator()
    dev.vep_mode([1, None, 20, 30, 40, 50])
    dev.erp_mode(3)
