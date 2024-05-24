import json
from opentrons import protocol_api
import numpy as np
from opentrons import types

requirements = {'robotType': 'OT-2', 'apiLevel': '2.10'}
metadata = {"protocolName": "Proxy Viscometer Protocol",
            'description': """This protocol is branched from https://www.rsc.org/suppdata/d2/dd/d2dd00126h/d2dd00126h1.pdf, 
            modified for the labware in the AC Lab. Have made it more modular (repeated blocks of code are functions), 
            and the parameters are more suited for our lab equipment. Future plans to use the custom function definitions defined here https://github.com/AdReNa-lab/OT2/blob/main/Custom_functions/custom_pipetting.py,
              to make it more optimal. """}

############################################################
### These functions are designed as protocol tools to be used in other functions ###
def get_tip_length(pipette: types.Mount):
    # Get tip length currently in use for a pipette
    tip_racks = pipette._tip_racks[0]
    tip_length = tip_racks.tip_length
    return tip_length

def get_default_flow_rates(pipette: types.Mount):
    default_flow_rates = {}
    default_flow_rates['aspirate'] = pipette._implementation._flow_rates.aspirate
    default_flow_rates['dispense'] = pipette._implementation._flow_rates.dispense
    default_flow_rates['blow_out'] = pipette._implementation._flow_rates.blow_out
    return default_flow_rates
############################################################

def set_c_info(well: types.Location, c_info: dict):
    # Set the c_info dictionary attribute of a well from a properly formatted dictionary
    well._geometry.custom_well_info = c_info
def get_c_info(well: types.Location):
    # Read and returns the c_info attribute of a well
    c_info = well._geometry.custom_well_info
    return c_info
############################################################

def get_h_from_v(well: types.Location, volume: float):
    # Converts a volume in headroom for a particular well
    info = get_c_info(well)
    h_given_v = info['vh_functions']['h_given_v']
    headroom = h_given_v(volume)
    return headroom
def get_v_from_h(well: types.Location, headroom: float):
    # Converts a headroom in volume for a particular well
    info = get_c_info(well)
    v_given_h = info['vh_functions']['v_given_h']
    volume = v_given_h(headroom)
    return volume
############################################################

def set_headroom(well: types.Location, headroom: float):
    # Set the headroom and volume attributes of a well from a headroom input
    info = get_c_info(well)
    info['headroom'] = headroom
    volume = get_v_from_h(well, headroom)
    info['volume'] = volume
    set_c_info(well, info)
def get_headroom(well: types.Location):
    # Reads and return the headroom of a well
    info = get_c_info(well)
    headroom = info['headroom']
    return headroom
############################################################

def set_volume(well: types.Location, volume: float):
    # Set the headroom and volume attributes of a well from a volume input
    info = get_c_info(well)
    info['volume'] = volume
    headroom = get_h_from_v(well, volume)
    info['headroom'] = headroom
    set_c_info(well, info)
def get_volume(well: types.Location):
    # Reads and return the volume of a well
    info = get_c_info(well)
    volume = info['volume']
    return volume
############################################################

def get_relative_from_flow_rate_aspirate(pipette: types.Mount, flow_rate: float):
    # Converts a flow rate in uL/s in a ratio of the default aspirate flow rate 
    flow_rates = get_default_flow_rates(pipette)
    default_aspirate = flow_rates['aspirate']
    relative_flow_rate = flow_rate/default_aspirate
    return relative_flow_rate
def get_relative_from_flow_rate_dispense(pipette: types.Mount, flow_rate: float):
    # Converts a flow rate in uL/s in a ratio of the default dispense flow rate 
    flow_rates = get_default_flow_rates(pipette)
    default_dispense = flow_rates['dispense']
    relative_flow_rate = flow_rate/default_dispense
    return relative_flow_rate
############################################################

def set_constituent(well: types.Location, 
                    constituent: str,
                    concentration: float,
                    c_uncertainty: float = 0,
                    v_uncertainty: float = 0):
    """
    This function is used to input concentration and uncertainties information of a constituent in a protocol.
    
    - constituent is a string containing the name used to designate the constituent throughout the protocol
    - concentration is given in ng/ml of the constituent
    - uncertainties on the concentration are split between a random and systematic one. 
      If one is 0 or unknown, it doesn't need to be inputed (defaults to 0)
    """
    c_info = get_c_info(well)
    c_info['constituents_number'] += 1
    c_info['constituents'].append(constituent)
    c_info['concentrations_stock'][constituent] = concentration
    c_info['concentration_uncertainty_stock'][constituent] = c_uncertainty
    c_info['volume_stock'][constituent] = get_volume(well)
    c_info['volume_uncertainty_stock'][constituent] = v_uncertainty
    set_c_info(well, c_info)
def get_constituents(well: types.Location):
    # This function reads and returns all the constituents present in a well
    c_info = get_c_info(well)
    constituents = c_info['constituents']  
    return constituents
############################################################

def set_pipette_uncertainties(pipette: types.Mount,
                              vu_function: list):
    # This function creates an attribute for a pipette allowing calculation of uncertainties 
    # on volumes transferred with this pipette
    uncertainties_functions = {
        'random': vu_function[0],
        'systematic': vu_function[1]
    }
    pipette.uncertainties_dict = uncertainties_functions
def get_pipette_uncertainties(pipette: types.Mount):
    # This function reads and return the volume uncertainties functions linked to a pipette

    return pipette.uncertainties_dict
############################################################

def get_concentration(well: types.Location,
                      constituent: str):
    # Reads and returns the concentration and uncertainty of a constituent in a well. Dependent on stored stock information
    c_info = get_c_info(well)
    
    try:
        # Extracts info from the well
        stock_volume = c_info['volume_stock'][constituent]
        # Volume of the well is corrected for the systematic uncertainty in calculations
        corrected_well_volume = get_volume(well) + c_info['volume_uncertainty']['systematic']
        well_volume_unc = c_info['volume_uncertainty']['random']
        stock_concentration = c_info['concentrations_stock'][constituent]
        stock_c_unc = c_info['concentration_uncertainty_stock'][constituent]
        stock_v_unc = c_info['volume_uncertainty_stock'][constituent]
        # Calculates concentration and uncertainty in the well
        stock_ratio = stock_volume/corrected_well_volume
        concentration = stock_ratio*stock_concentration
        # Lower-end calculation, considering stock volume as a constant without associated uncertainty 
        # (i.e. fully correlated to well volume)
        low_c_unc_pc = np.sqrt((stock_c_unc/stock_concentration)**2 + (well_volume_unc/corrected_well_volume)**2)
        low_c_unc = low_c_unc_pc*concentration
        # Higher-end calculation, considering stock volume as independent from well volume, with own unertainty 
        high_c_unc_pc = np.sqrt((stock_v_unc/stock_volume)**2 + (stock_c_unc/stock_concentration)**2 + (well_volume_unc/corrected_well_volume)**2)
        high_c_unc = high_c_unc_pc*concentration
        # Returns the concentration and uncertainty in the same unit (not in %)
        return concentration, low_c_unc, high_c_unc
        
    except KeyError:
        print('Warning, constituent {} is not present in well {}'.format(constituent,well))
        return 0,0,0
############################################################
### This function is used to initiate well attributes ###
def initiate_well(well: types.Location, 
                  volume_function: list):
    """
    This function is used to initiate a well's custom attributes. Those attributes are regrouped as a dictionary 
    with default values as follows:
    
    - Numerical values as 0
    - Headroom and vh_functions specific to the well
    - concentrations and uncertainties are dependent on thesubstances used in the protocol 
      and thus initiated as 'None' or left empty
    """
    c_info = {'constituents_number': 0, 
              'volume': 0,
              'headroom': None,
              'vh_functions': {
                  'v_given_h': None,
                  'h_given_v': None},
              'volume_uncertainty': {
                  'random': 0,
                  'systematic': 0},
              'constituents': [], 
              'concentrations_stock': {},
              'concentration_uncertainty_stock': {},
              'volume_stock': {},
              'volume_uncertainty_stock': {}
             }
    
    c_info['headroom'] = well._geometry._depth
    c_info['vh_functions']['v_given_h'] = volume_function[0]
    c_info['vh_functions']['h_given_v'] = volume_function[1]
    set_c_info(well, c_info)
############################################################

def print_solution_info(well: types.Location):
    # Reads and print the entire dictionary 'c_info' of a well
    c_info = get_c_info(well)
    #return (well, c_info)
    print('\nInformation of well {}:'.format(well))
    for key, val in c_info.items():
        print(key, ': ', val)
    print()
def print_constituent_concentration(well: types.Location,
                                    constituent: str,
                                    label: str = None):
    info = get_c_info(well)
    if label:
        name = label
    else:
        name = well
    
    if constituent in info['constituents']:
        concentration, low_unc, high_unc = get_concentration(well, constituent)
        print('\nConcentration of constituent {} in well {} is {} \u00B1 ({} - {}) ng/mL'.format(constituent, name, round(concentration, 2), round(low_unc, 2), round(high_unc, 2)))
    else:
        print('\nConstituent ' + constituent + ' is not present in well: ' +str(well))
############################################################

def custom_aspirate(pipette: types.Mount,
                    transfer_volume: float,
                    location: types.Location,
                    immersion_depth: float = 2,
                    safety_height: float = 0.5,                    
                    rate: float = 75):
    """
    Custom aspiration function
    By default: aspirates 2 mm below the meniscus level
    
    Function-specific arguments:
    - immersion_depth (in mm) beneath meniscus
    - safety_height prevents the tip from crashing into bottom of the well
    - rate in uL/s
    """
    # Arguments checking
    assert transfer_volume > 0
    assert safety_height >= 0
    
    # Conversion from a rate in ul/s to a relative rate
    rate_rel = bb.get_relative_from_flow_rate_aspirate(pipette, rate)
    
    # Extraction or calculation of headrooms and volumes before and after aspiration
    initial_volume = bb.get_volume(location)
    final_volume = initial_volume - transfer_volume
    initial_headroom = bb.get_headroom(location)
    final_headroom = bb.get_h_from_v(location, final_volume)
    
    # depth_to_aspirate is the distance from the top of the well at which aspiration will take place
    depth_to_aspirate = final_headroom + immersion_depth
    
    # Modifies the headroom in the well attributes
    bb.set_headroom(location, final_headroom)
    
    # Safety checking
    # ...avoidance of these errors are also covered by the use 
    # of specified extrapolation fill_values in the gradations_to_vh() function
    
    # Low volume/aspiration height warning
    depth = bb.get_h_from_v(location, 0)
    if depth_to_aspirate > depth - safety_height:
        depth_to_aspirate = depth - safety_height  # e.g. 0.5mm above the bottom of the well
        print('Warning, aspiration height for well ' +str(location) +' is lower than ' +str(safety_height) +' mm')
    
    # Avoids tip submersion in liquid
    tip_length = bb.get_tip_length(pipette)
    if depth_to_aspirate > 0.8*tip_length + initial_headroom:  # Checks that the pipette tip will not be fully submerged
        depth_to_aspirate = 0.8*tip_length + initial_headroom
        print('Warning, aspiration depth was set lower then pipette tip length, it has been changed to ' +str(depth_to_aspirate))
    
    if depth_to_aspirate < 0: 
        depth_to_aspirate = 0 # i.e. at the top of the well
        
    pipette.aspirate(transfer_volume, location.top(-depth_to_aspirate), rate = rate_rel)
    return #return None explicitly

def run(protocol: protocol_api.ProtocolContext):
    
    CALAB_8_TUBERACK_20000UL_DEF_JSON = """{"ordering":[["A1","B1"],["A2","B2"],["A3","B3"],["A4","B4"]],
    "brand":{"brand":"CALAB","brandId":[]},
    "metadata":{"displayName":"CALAB 8 Tube Rack with Generic 20 mL","displayCategory":"tubeRack","displayVolumeUnits":"µL","tags":[]},
    "dimensions":{"xDimension":127.76,"yDimension":85.47,"zDimension":60.75},
    "wells":{"A1":{"depth":55.55,"totalLiquidVolume":20000,"shape":"circular","diameter":27.15,"x":16.5,"y":68.97,"z":5.2},
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
    tiprack_1.set_offset(x=0.5, y=-1.4, z=2.2)

    # Define reservoir 
    reservoir = protocol.load_labware('calab_8_tuberack_20000ul', 10) 
    reservoir.set_offset(x=0.2, y=-1.7, z=0.9)

    # Define plate
    plate = protocol.load_labware('corning_96_wellplate_360ul_flat', 5)      
    plate.set_offset(x=1, y=0.0, z=0.0)

    # Define pipettes
    p300 = protocol.load_instrument('p300_single_gen2', mount='left', tip_racks=[tiprack_1])

    #************ Initialization Parameters ************
    samples_ran = 0
    no_of_samples = 1 

    adepth = 0 
    depth = -50

    asptime = 5
    disptime = 5
    
    fr_arr = [10] # dispensed flowrate in uL/s
    well_touch_depth = 0
    touch_tip_speed = 60 

    res_letter_list = ["A", "B"]  #reservoir positions (of the custom defined calab_8_tuberack_20000ul)
    well_letter_list = ["A", "B", "C", "D", "E", "F", "G", "H"] #well positions (of the corning_96_wellplate_16.8ml_flat) --> 8 x 12 well plate 
    tube_rack_list = [f'{row}{col}' for row in 'AB' for col in range(1,5)]
    well_plate_list = [f"{row}" for row in "ABCDEFGH"]
    well_ind_list= [f'{col}' for col in range (1, 13)]
    #************  ************

    protocol.set_rail_lights(on=True)

    i = 0
    #dummy run - systematic error correction of exterior excess weight
    if i == 0:
        p300.pick_up_tip() #pick up pipette tip from tip rack 

        #move to reservoir 
        p300.move_to(reservoir[tube_rack_list[samples_ran]].top()) #moves the pipette tip to the top of the reservoir tube  (depth of 55.55 for the CALAB) 
        protocol.delay(seconds=2) #actual trial should delay for 10

        cp.custom_touch_tip(pipette=p300, well=reservoir[tube_rack_list[samples_ran]], radius_offset=1, depth=-10, speed=touch_tip_speed, increments=2)

        #move to plate 
        p300.move_to(plate[well_plate_list[samples_ran] + well_ind_list[0]].top())    # move to top of well plate
        protocol.delay(seconds=2) #actual trial should delay for 5

        #cp.custom_touch_tip(pipette=p300, well=reservoir[tube_rack_list[samples_ran]], radius_offset=1, depth=-10, speed=touch_tip_speed, increments=2) 
        p300.move_to(reservoir[tube_rack_list[samples_ran]].top())
        protocol.pause("Time to measure.")  # take mass reading (will be the empty plate only during trial run)

        cp.custom_touch_tip(pipette=p300, well=reservoir[tube_rack_list[samples_ran]], radius_offset=1, depth=-10, speed=touch_tip_speed, increments=2)
        for e in range(15):
            p300.blow_out() #blows out over current location


        #for actual runs, 3 trials each measurement
    while samples_ran < no_of_samples:
        for t in range(3):
            p300.pick_up_tip()
            trans_vol = 100.0
            imm_depth = 3
            safe_height = 5
            flowrate = 30
            
            cp.custom_aspirate(pipette=p300, transfer_volume=trans_vol, location=plate[tube_rack_list[samples_ran]], immersion_depth=imm_depth, safety_height=safe_height,  rate=flowrate) #avoids submerging the tip in the liquid
            #custom_aspirate(pipette: types.Mount,: float,location: types.Location,immersion_depth: float = 2,safety_height: float = 0.5,rate: float = 75):
            
            #wait for the excess to drip off 
            if trans_vol <= 100:
                protocol.delay(seconds=10) 
            elif 100 < trans_vol <= 600:  
                protocol.delay(seconds=20)          
            else:

                protocol.delay(seconds=30)

            #wipe off excess on edge
            cp.custom_touch_tip(pipette=p300, well=reservoir[tube_rack_list[samples_ran]], radius_offset=1, depth=-10, speed=touch_tip_speed, increments=2)

            #dispense
            cp.custom_dispense(pipette=p300, transfer_volume=trans_vol, location=(well_plate_list[samples_ran] + well_ind_list[t]), immersion_depth=imm_depth, safety_height=safe_height, rate=flowrate)

            #wait for the excess to drip off
            protocol.delay(seconds=10)

            p300.move_to(reservoir[tube_rack_list[samples_ran]].top()) #moves the pipette tip to the top of the reservoir tube  
            protocol.pause() #pause to measure the liquid dipsened on the well plate; resume once done measuring the change in mass and place the plate back
            for e in range(15):
                p300.blow_out() 
                
            p300.drop_tip() #drop the pipette tip into trash


        samples_ran += 1

    