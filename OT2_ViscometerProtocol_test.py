from opentrons import protocol_api
import json

requirements = {'robotType': 'OT-2', 'apiLevel': '2.10'}
metadata = {"protocolName": "Proxy Viscometer Protocol",
            'description': """This protocol is the same used in https://www.rsc.org/suppdata/d2/dd/d2dd00126h/d2dd00126h1.pdf
            modified for the labware in the SDL. Future plans to optimize the liquid handling (https://github.com/Quijanove/LiqTransferOptimizer/blob/main/MOBO_liquid_handling_paramters.ipynb) 
            and for automatic mass balancing, to automatically calculate the dispense rate of the viscous liquid."""}


def run(protocol: protocol_api.ProtocolContext):

    #************ Definitions ************
    # double check the load locations

    #Custom reservoir
    CALAB_8_TUBERACK_20000UL_DEF_JSON = """{"ordering":[["A1","B1"],["A2","B2"],["A3","B3"],["A4","B4"]],
    "brand":{"brand":"CALAB","brandId":[]},
    "metadata":{"displayName":"CALAB 8 Tube Rack with Generic 20 mL","displayCategory":"tubeRack","displayVolumeUnits":"µL","tags":[]},
    "dimensions":{"xDimension":127.76,"yDimension":85.47,"zDimension":60.75},"wells":{"A1":{"depth":55.55,"totalLiquidVolume":20000,"shape":"circular","diameter":27.15,"x":16.5,"y":68.97,"z":5.2},
    "B1":{"depth":55.55,"totalLiquidVolume":20000,"shape":"circular","diameter":27.15,"x":16.5,"y":37.97,"z":5.2},
    "A2":{"depth":55.55,"totalLiquidVolume":20000,"shape":"circular","diameter":27.15,"x":47.5,"y":68.97,"z":5.2},
    "B2":{"depth":55.55,"totalLiquidVolume":20000,"shape":"circular","diameter":27.15,"x":47.5,"y":37.97,"z":5.2},
    "A3":{"depth":55.55,"totalLiquidVolume":20000,"shape":"circular","diameter":27.15,"x":78.5,"y":68.97,"z":5.2},
    "B3":{"depth":55.55,"totalLiquidVolume":20000,"shape":"circular","diameter":27.15,"x":78.5,"y":37.97,"z":5.2},
    "A4":{"depth":55.55,"totalLiquidVolume":20000,"shape":"circular","diameter":27.15,"x":109.5,"y":68.97,"z":5.2},
    "B4":{"depth":55.55,"totalLiquidVolume":20000,"shape":"circular","diameter":27.15,"x":109.5,"y":37.97,"z":5.2}},
    "groups":[{"brand":{"brand":"Generic","brandId":[]},"metadata":{"wellBottomShape":"flat","displayCategory":"tubeRack"},
    "wells":["A1","B1","A2","B2","A3","B3","A4","B4"]}],
    "parameters":{"format":"irregular","quirks":[],"isTiprack":false,"isMagneticModuleCompatible":false,"loadName":"calab_8_tuberack_20000ul"},
    "namespace":"custom_beta","version":1,"schemaVersion":2,"cornerOffsetFromSlot":{"x":0,"y":0,"z":0}}"""

    calab_8_tuberack_20000ul = json.loads(CALAB_8_TUBERACK_20000UL_DEF_JSON)

    # Define tips
    tiprack_1 = protocol.load_labware('opentrons_96_tiprack_300ul', 11)
    tiprack_1.set_offset(x=-0.2, y=-0.4, z=0.0)

    # Define reservoir 
    reservoir = protocol.load_labware('calab_8_tuberack_20000ul', 10) 
    reservoir.set_offset(x=0.6, y=-1.7, z=0.9)

    # Define plate
    plate = protocol.load_labware('corning_96_wellplate_360ul_flat', 5)        
    plate.set_offset(x=-0.10, y=-0.1, z=0.3)

    # Define pipettes
    p1000 = protocol.load_instrument('p1000_single_gen2', mount='right', tip_racks=None) #not used in the protocol
    p300 = protocol.load_instrument('p300_single_gen2', mount='left', tip_racks=[tiprack_1])

    #************ Initialization Parameters ************
    fr_arr            = [30]  # CAN CHANGE: dispensed flowrate/uL/s
    samples_ran       = 0     # DON'T CHANGE: initialisation counter
    no_of_samples     = 1    # CAN CHANGE: number of samples to run 
    adepth            = 0    # initialisation - will account for what depth to aspirate from depending on past history of volume dispensed
    depth             = -80  # 80 mm from top corresponds to ~ 12.5 mL: fill the reservoir tubes to approx. 20 mL
    asptime           = 5  # CAN CHANGE: protocol aspiration time fixed to 7.5 seconds
    disptime          = 5    # CAN CHANGE: protocol dispense time fixed to 5 seconds
    well_touch_depth  = 0    # touch_tip height on dispense plate (Corning 6-well plate)

    # Location of stored liquids & destinations
    res_letter_list = ["A", "B"]  #reservoir positions (of the custom defined calab_8_tuberack_20000ul)
    well_letter_list = ["A", "B"] #well positions (of the corning_6_wellplate_16.8ml_flat)

    #************ Protocol ************                      
    while samples_ran < no_of_samples:
        i = 0
        # "dummy run" - systematic error correction of exterior excess weight
        if i == 0:

            #pick up pipette tip 
            p300.pick_up_tip(tiprack_1["A" + str(samples_ran+1)]) 


            for e in range(3):
                #triplicate measurements - pipette directed to same position, mass measurements in between to distinguish mass added each time

                #reservoir section
                p300.move_to(reservoir[str(res_letter_list[samples_ran])+"1"].top(z=depth))    # CAN CHANGE: z = depth move to the reservoir well, without aspirating. 
                protocol.delay(seconds=10)  # 10 second asp_delay

                # tube touch tip (taps twice inside, taps twice on its way up)
                for e in range(2):
                    p300.touch_tip(radius=1.0, v_offset=-10)     # SHOULD CHANGE: radius. touch the pipette tip across the 4 opposite walls 10 mm into the falcon tube x2
                p300.touch_tip(radius=1.0, v_offset=-1)          # SHOULD CHANGE: radius. touch tip @ 1 mm into the falcon tube
                p300.touch_tip(radius=1.1, v_offset=0)         # SHOULD CHANGE: radius. touch tip @ the top of the falcon tube

                # plate touch tip
                p300.move_to(plate[str(well_letter_list[samples_ran]) + "1"].top())    # move to position on well plate
                protocol.delay(seconds=5)   # 5 second dispense delay
                p300.touch_tip(plate[str(well_letter_list[samples_ran]) + "1"], v_offset=well_touch_depth, speed=400)  # touch the pipette tip at the surface of the well plate; maybe change speed if too aggressive
                p300.move_to(reservoir[str(res_letter_list[samples_ran])+"1"].top())   # return the tip to the top of the well plate - during an actual run with fluid

                # fluid would be dispensed here in the actual trial

                #take a mass reading TO DO: make auatomatic 
                protocol.pause("Time to measure.")  # TO DO: make automatic 
                p300.touch_tip(v_offset=-10)
            for e in range(10):     # 10 blowout cycles to dispose any residual material in the pipette tip
                p300.blow_out(reservoir[str(res_letter_list[samples_ran])+"1"]) #blows out extra air at the specified location (reservoir)

        # handling of viscous fluids
        for e in range(3):  # triplicate measurements
            # aspirate liquid
            depth -= adepth #moves the depth of the pipette tip by the amount of liquid aspirated 
            asp_vol = fr_arr[i]*asptime
            asp_loc = reservoir[str(res_letter_list[samples_ran])+"1"].top(z=depth)
            p300.aspirate(asp_vol, asp_loc, rate=100/274.7)  #rate =  multiplies the default flow rate by that value
            #.aspirate(aspiration volume, well location, pipette flow rate)


            # aspiration delay
            if asp_vol <= 100:
                protocol.delay(seconds=10) 
            elif 100 < asp_vol <= 600:  # 375 uL falls within this category
                protocol.delay(seconds=20)          # 20 second aspiration delay
            else:
                protocol.delay(seconds=30)


            #wipe tip off 
            for e in range(2):  # touch tip x 2 @ -10 mm from top, x 1 @ -1 mm from top, x1 @ top
                p300.touch_tip(radius=1, v_offset=-10)
            p300.touch_tip(radius=1, v_offset=-1)
            p300.touch_tip(radius=1.1, v_offset=0)
        
        # dispense liquid
            disp_vol = fr_arr[i]*disptime
            disp_loc = plate[str(well_letter_list[samples_ran]) + "1"].top(10) #moves it to 10 above the top of the well
            p300.dispense(disp_vol, disp_loc, rate=float(fr_arr[i]/274.7))
            p300.touch_tip(v_offset=well_touch_depth, speed=400)
            p300.move_to(reservoir[str(res_letter_list[samples_ran])+"4"].top()) #moves back to the reservoir well (above 4) 

        #TO DO: make automatic 
            protocol.pause("Time to measure.") 
        
        # getting rid of excess liquid
        # this seems a little bit excessive ? 
            p300.dispense(1000, reservoir[str(res_letter_list[samples_ran])+"1"].top(), rate=100/274.7)
            protocol.delay(seconds=20)
            p300.aspirate(400, reservoir[str(res_letter_list[samples_ran])+"1"].top(), rate=100/274.7)
            protocol.delay(seconds=10)
            p300.dispense(400, reservoir[str(res_letter_list[samples_ran])+"1"].top(), rate=100/274.7)
            p300.touch_tip(v_offset=-10)
            for e in range(10):
                p300.blow_out(reservoir[str(res_letter_list[samples_ran])+"1"])
            
        # add 1mm of depth for every 10000/9ul aspirated from falcon tube
            tdisp = disp_vol/1000.0
            adepth = tdisp * (9/5)  # 5ml is 9mm (this might have to be changed for our labware)
        
        i += 1  # useful if you wish to test multiple flow rates
        

        #executes if i != 0 and == number of different flow rates you want to try
        if i == len(fr_arr): 

            for e in range(3):

                #reservoir section
                p300.move_to(reservoir[str(res_letter_list[samples_ran])+"1"].top(z=depth))
                protocol.delay(seconds=10)

                for e in range(2):
                    p300.touch_tip(radius=0.9, v_offset=-8) #radius is percent of the total well radius, v_offset is the distance below the top of the well (-ve)
                p300.touch_tip(radius=0.9, v_offset=-1)
                p300.touch_tip(radius=0.9, v_offset=0)

                #plate touch tip
                p300.move_to(plate[str(well_letter_list[samples_ran]) + "1"].top())
                protocol.delay(seconds=5)
                p300.touch_tip(plate[str(well_letter_list[samples_ran]) + "1"], v_offset=well_touch_depth, speed=400)  # speed = 400mm/s
                p300.move_to(reservoir[str(res_letter_list[samples_ran])+"1"].top())
                protocol.pause("Time to measure.")
                p300.touch_tip(v_offset=-10)
            for e in range(10):
                p300.blow_out(reservoir[str(res_letter_list[samples_ran])+"1"])
            p300.drop_tip()
            
        samples_ran += 1
        depth = -80     