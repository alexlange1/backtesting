#!/usr/bin/env python3
"""
TAO20 Real Historical Backtest
================================
Uses actual TAO20 portfolio weights from September 14th and October 12th.
Fetches live price data and calculates NAV with APY.

Author: Alexander Lange
Date: October 22, 2025
"""

import os
import json
import re
import subprocess
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

NETWORK = 'finney'
ARCHIVE_NODE = 'wss://archive.chain.opentensor.ai:443'
BLOCKS_PER_DAY = 7200
START_NAV = 1.0

# Real TAO20 portfolio weights
# TAO20 Index Weights by Period
# Generated from backtest analysis

# Period 1: 20250214 to 20250227
FEB_27_WEIGHTS = {
    4: 0.16958017136579417,
    64: 0.1551799599286539,
    8: 0.10089311369593285,
    34: 0.09765592428092783,
    51: 0.07943444562343537,
    19: 0.06526124275277442,
    42: 0.036930202275635225,
    13: 0.03091524730733701,
    1: 0.030122925680262064,
    10: 0.029878662021851014,
    53: 0.02687143888577648,
    46: 0.023827799733560116,
    11: 0.02297346653705745,
    5: 0.02211246818159272,
    9: 0.021040177384067292,
    3: 0.01977930133827604,
    6: 0.01731849810460033,
    56: 0.01723633133631757,
    30: 0.01683624009060555,
    45: 0.01615238347554259,
}

# Period 2: 20250228 to 20250313
MAR_13_WEIGHTS = {
    4: 0.16119636856491376,
    64: 0.15778373758896744,
    8: 0.14971578671339383,
    34: 0.08683382555343865,
    51: 0.07277110108731372,
    19: 0.047057356921679165,
    13: 0.031930583122370605,
    52: 0.03092439020273166,
    72: 0.03028180841251709,
    68: 0.0289302379680541,
    3: 0.02838226821088267,
    1: 0.027940558125570933,
    10: 0.02509901034824404,
    56: 0.021215540790045,
    11: 0.01887100908931416,
    9: 0.017555929369519756,
    42: 0.017229658036632522,
    53: 0.016170470117750795,
    5: 0.016008316002028455,
    25: 0.014102043774631676,
}

# Period 3: 20250314 to 20250327
MAR_27_WEIGHTS = {
    64: 0.1787606815491337,
    4: 0.14446121403279433,
    8: 0.1389224739787455,
    51: 0.08405609850056804,
    34: 0.07652284881740166,
    19: 0.04768578457842242,
    52: 0.03891715421564976,
    3: 0.03505711739937578,
    13: 0.03430217928033592,
    1: 0.030983237138215085,
    56: 0.030666825677747398,
    10: 0.023585063303581923,
    68: 0.02297829556619187,
    43: 0.020692863972848297,
    53: 0.019651671720736202,
    42: 0.015348404831555184,
    5: 0.014801908103354848,
    25: 0.01450388167406493,
    9: 0.014313704068008373,
    72: 0.013788591591268783,
}

# Period 4: 20250328 to 20250410
APR_10_WEIGHTS = {
    64: 0.20677126039338078,
    4: 0.12942188809121874,
    8: 0.09646134172703617,
    56: 0.07691439269476824,
    3: 0.06309867227562092,
    51: 0.056155496794587305,
    19: 0.047731101088458586,
    1: 0.038344777207916306,
    34: 0.03765288375988897,
    13: 0.03440440345122877,
    68: 0.03321782200754898,
    52: 0.030682718959456432,
    81: 0.03062524809990516,
    75: 0.027716031231403284,
    17: 0.022384868615650196,
    25: 0.015243914968485725,
    10: 0.014351672590556839,
    53: 0.013450143271370979,
    43: 0.013391208005871924,
    44: 0.011980154765645732,
}

# Period 5: 20250411 to 20250424
APR_24_WEIGHTS = {
    64: 0.20703696487735557,
    56: 0.10291095574150623,
    4: 0.09793405744755655,
    8: 0.0843260141394196,
    3: 0.06542263518826004,
    19: 0.056511793843632516,
    51: 0.05576036155803102,
    68: 0.046118798045172785,
    81: 0.03554637264903707,
    1: 0.033683826923828056,
    75: 0.0331365033002312,
    13: 0.03253919298662897,
    34: 0.02885711772090384,
    17: 0.02635898284683459,
    52: 0.02484708722455269,
    44: 0.019640121565463076,
    25: 0.014760163771651605,
    9: 0.013134381582213353,
    43: 0.01084704422304367,
    33: 0.01062762436467749,
}

# Period 6: 20250425 to 20250508
MAY_08_WEIGHTS = {
    64: 0.1848103422326239,
    8: 0.09734429207522258,
    4: 0.0902871739518772,
    56: 0.08121978437894854,
    51: 0.07831237708519767,
    3: 0.06512702555594163,
    14: 0.05939420158799571,
    19: 0.042655642483734796,
    1: 0.0400972649521562,
    68: 0.034146155168582125,
    13: 0.029233180542273345,
    34: 0.026068358175967764,
    5: 0.02510276694153109,
    81: 0.02470977874494522,
    17: 0.022317285696512607,
    75: 0.02076122294530255,
    52: 0.020250343693588028,
    44: 0.01975148468672916,
    85: 0.01937385535889311,
    9: 0.019037463741976766,
}

# Period 7: 20250509 to 20250522
MAY_22_WEIGHTS = {
    64: 0.1803600879125956,
    14: 0.10236697220976575,
    4: 0.08582173418961996,
    56: 0.07888364565576093,
    51: 0.07113662193439799,
    3: 0.06787312936970913,
    8: 0.06470349672826829,
    5: 0.043419457007556506,
    19: 0.03865047074766818,
    1: 0.03554948903716509,
    68: 0.029999786079592024,
    17: 0.02657953203328625,
    34: 0.025325746006136886,
    81: 0.02484223734119353,
    13: 0.024636708279628296,
    44: 0.021480612207189758,
    9: 0.020971708858346243,
    10: 0.01961275637752479,
    52: 0.019118604692563133,
    85: 0.018667203332031628,
}

# Period 8: 20250523 to 20250605
JUN_05_WEIGHTS = {
    117: 0.38570285784234737,
    64: 0.12029131660090805,
    14: 0.06266715903483983,
    56: 0.05242513356920597,
    4: 0.050031575949758406,
    3: 0.04932910460748912,
    51: 0.04155852542362774,
    8: 0.030371302849567784,
    5: 0.02661398307522643,
    9: 0.023362863459326897,
    19: 0.022955147359694894,
    1: 0.018004485387021155,
    68: 0.01685734734588558,
    17: 0.016775061767050157,
    44: 0.015627792931539885,
    13: 0.015368221303670285,
    34: 0.015192166529543858,
    10: 0.014215041693190477,
    81: 0.011440804453374193,
    33: 0.011210108816731946,
}

# Period 9: 20250606 to 20250619
JUN_19_WEIGHTS = {
    123: 0.20087958744198445,
    64: 0.15618294273550626,
    14: 0.0657551931022206,
    3: 0.0649676330286382,
    4: 0.06044091372312322,
    56: 0.05972904101027733,
    51: 0.05633602698746628,
    124: 0.05021989686049611,
    5: 0.0402372495920556,
    8: 0.03864458090545131,
    9: 0.03029440073813879,
    19: 0.02633734550935176,
    17: 0.022578818873755076,
    44: 0.021977496977564598,
    68: 0.020607340902493294,
    13: 0.019996210809346483,
    1: 0.019424291557930094,
    34: 0.018426606464113614,
    10: 0.013713244610597192,
    33: 0.01325117816948974,
}

# Period 10: 20250620 to 20250703
JUL_03_WEIGHTS = {
    128: 0.38963255600427554,
    123: 0.19856415746321127,
    64: 0.08369434287766533,
    51: 0.036564262351675376,
    3: 0.035075650994236936,
    4: 0.03403086392676236,
    56: 0.031227405075085812,
    8: 0.023481984792872113,
    5: 0.022129598764698864,
    14: 0.01962436375236002,
    44: 0.017108525008676455,
    9: 0.016974986333125625,
    19: 0.014738961168822184,
    17: 0.01320780447244819,
    1: 0.012216490593276293,
    34: 0.012110566820291581,
    13: 0.011604103890706978,
    68: 0.010587827445095344,
    33: 0.009154391307321085,
    39: 0.008271156957392693,
}

# Period 11: 20250704 to 20250717
JUL_17_WEIGHTS = {
    127: 0.5159946133540754,
    64: 0.09120431321560926,
    51: 0.05068122854785201,
    4: 0.038156913570707884,
    3: 0.03741664187505516,
    56: 0.03432523744283325,
    8: 0.028313414736181448,
    5: 0.02079515641700847,
    44: 0.020566384068659713,
    9: 0.019045849933537477,
    14: 0.01712147821193742,
    17: 0.01673892866489405,
    34: 0.015303977735753949,
    33: 0.014985240117899734,
    19: 0.014154337231792326,
    39: 0.014077845560374988,
    1: 0.013875559903259393,
    68: 0.012850704091778825,
    13: 0.012837267282027186,
    63: 0.011554908038762163,
}

# Period 12: 20250718 to 20250731
JUL_31_WEIGHTS = {
    64: 0.18595775182449295,
    51: 0.09359187436014786,
    56: 0.08636675335084847,
    3: 0.085166350201984,
    4: 0.08052007640648863,
    8: 0.05979103224800399,
    9: 0.04266232938154363,
    5: 0.03602179242498641,
    44: 0.03592774204696413,
    63: 0.032131006946978714,
    17: 0.03184014765436252,
    14: 0.03162333576080626,
    33: 0.0286089235497299,
    34: 0.02700265292509178,
    19: 0.026556906621733205,
    1: 0.02510340458841338,
    68: 0.024199102835743794,
    13: 0.02374348549985101,
    39: 0.022305700067170666,
    62: 0.020879631304658773,
}

# Period 13: 20250801 to 20250814
AUG_14_WEIGHTS = {
    64: 0.17673138193045743,
    51: 0.08324409157183457,
    4: 0.07752913146242586,
    120: 0.07676571747029116,
    3: 0.07204032234388379,
    56: 0.07008281898005995,
    8: 0.06129043276144011,
    9: 0.04167925838371205,
    5: 0.03770605230146783,
    44: 0.036878953148807854,
    62: 0.03371835376032939,
    14: 0.03006093338010352,
    33: 0.02867042277850792,
    34: 0.02775542007721293,
    39: 0.025243886963745802,
    19: 0.024941547907147137,
    63: 0.024686552956805677,
    11: 0.024234754244858367,
    1: 0.023370505382821104,
    17: 0.023369462194087576,
}

# Period 14: 20250815 to 20250828
AUG_28_WEIGHTS = {
    64: 0.1602557071822771,
    120: 0.0917370883523958,
    51: 0.08674662416292078,
    4: 0.07212407764510614,
    62: 0.07123435736640645,
    3: 0.06804284258109213,
    56: 0.06292311323817285,
    8: 0.060898348172035245,
    9: 0.035128021542984444,
    5: 0.034783026822484166,
    44: 0.029687607750218628,
    34: 0.028198300934075854,
    93: 0.028142242100191627,
    11: 0.027886864813250745,
    39: 0.027437696554048648,
    33: 0.026279798251411073,
    19: 0.022533798481851573,
    63: 0.022360418176994256,
    14: 0.02185158937131527,
    13: 0.02174847650076714,
}

# Period 15: 20250829 to 20250911
SEP_11_WEIGHTS = {
    64: 0.15595807702812278,
    62: 0.11561211213793117,
    120: 0.10986631432394114,
    51: 0.08440238776788944,
    4: 0.06808241220791678,
    56: 0.05844114425238177,
    3: 0.05665938696673181,
    8: 0.05378862665351104,
    5: 0.034235845930501316,
    93: 0.029247915259331108,
    11: 0.027902556172516316,
    34: 0.02779253050242591,
    9: 0.026990326754414175,
    44: 0.02628507729320063,
    123: 0.023828271524638088,
    39: 0.021784437120303646,
    33: 0.02039966206790553,
    17: 0.01991383565467802,
    13: 0.019479645005948787,
    1: 0.019329435375710566,
}

# Period 16: 20250912 to 20250925
SEP_25_WEIGHTS = {
    64: 0.15153655595754698,
    120: 0.11147379243600072,
    62: 0.09824494471696214,
    51: 0.09169393290755132,
    4: 0.07171614473806238,
    56: 0.061899703809256565,
    8: 0.05479176828872188,
    3: 0.0532777333346883,
    5: 0.03888626023341147,
    93: 0.032271191124774654,
    44: 0.029227832047779144,
    34: 0.029147315414112078,
    11: 0.028947617536394566,
    9: 0.02598519776985478,
    50: 0.020768989429251455,
    41: 0.020540483530541297,
    35: 0.02028769505015864,
    123: 0.02007731380867265,
    33: 0.019809698586995727,
    17: 0.019415829279263247,
}

# Period 17: 20250926 to 20251009
OCT_09_WEIGHTS = {
    64: 0.13237706854223055,
    120: 0.11236321225163338,
    62: 0.10945419630732993,
    51: 0.09362815309941287,
    4: 0.07318108164234094,
    56: 0.05773944291830063,
    8: 0.05128339728003509,
    3: 0.04803986567824455,
    5: 0.03961024658599567,
    41: 0.03269192776603509,
    75: 0.030550479554787107,
    34: 0.030108192889802352,
    9: 0.029515644055833463,
    44: 0.02641265031376088,
    93: 0.02537914100432978,
    33: 0.02375609339162948,
    50: 0.022234253020195067,
    35: 0.02105098858794254,
    11: 0.020871145819785192,
    48: 0.01975281929037551,
}

# Period 18: 20251010 to 20251023
OCT_23_WEIGHTS = {
    64: 0.13126551649319135,
    62: 0.11024970355575361,
    120: 0.10750744160916768,
    51: 0.0949754491784894,
    4: 0.07627696993452263,
    56: 0.05453362373348235,
    8: 0.04919621134670221,
    3: 0.04488768854702722,
    5: 0.041317224499832994,
    41: 0.03253206882560766,
    9: 0.03236514372919765,
    34: 0.031317820983469635,
    75: 0.029987132118343262,
    44: 0.027237663055319224,
    33: 0.027086590802281804,
    93: 0.025223053254837594,
    121: 0.021735237909561132,
    17: 0.021644850185168627,
    48: 0.020343573259670795,
    115: 0.020317036978373202,
}

# APY Model (from previous implementation)
class AlphaAPYModel:
    TAO_PER_DAY = 7200
    ALPHA_MULTIPLIER = 2
    
    def estimate_staking_ratio(self, supply: float) -> float:
        if supply <= 0:
            return 0.15
        
        s1, r1 = 1.129, 0.2066
        s2, r2 = 3.166, 0.1838
        supply_m = supply / 1_000_000
        
        b = math.log(r2 / r1) / math.log(s2 / s1)
        a = r1 / (s1 ** b)
        estimated_ratio = a * (supply_m ** b)
        estimated_ratio = max(0.05, min(0.40, estimated_ratio))
        
        if supply_m < 0.1:
            calc_at_100k = a * (0.1 ** b)
            ratio_new = (supply_m / 0.1) * calc_at_100k + (1 - supply_m / 0.1) * 0.30
            return ratio_new
        
        return estimated_ratio
    
    def calculate_alpha_apy(self, emission_fraction: float, supply: float) -> Tuple[float, float, float]:
        daily_alpha = emission_fraction * self.TAO_PER_DAY * self.ALPHA_MULTIPLIER
        staked_ratio = self.estimate_staking_ratio(supply)
        staked_alpha = supply * staked_ratio
        
        if staked_alpha > 0:
            daily_yield = daily_alpha / staked_alpha
            apy = daily_yield * 365 * 100
        else:
            apy = 0.0
        
        return apy, staked_alpha, daily_alpha


def get_subnet_data() -> Dict[int, Dict]:
    """Fetch current subnet data for APY calculation."""
    logger.info("Fetching subnet data...")
    
    try:
        cmd = ['btcli', 'subnets', 'list', '--network', NETWORK, '--json-output']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            return {}
        
        cleaned = re.sub(r'\\n', ' ', result.stdout)
        cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
        data = json.loads(cleaned)
        subnets = data.get('subnets', {})
        
        apy_model = AlphaAPYModel()
        subnet_data = {}
        
        for netuid_str, subnet_info in subnets.items():
            netuid = int(netuid_str)
            emission = subnet_info.get('emission', 0)
            supply = subnet_info.get('supply', 0)
            
            if supply > 0:
                apy, staked, daily_emissions = apy_model.calculate_alpha_apy(emission, supply)
                subnet_data[netuid] = {
                    'emission': emission,
                    'supply': supply,
                    'alpha_apy': apy,
                    'name': subnet_info.get('subnet_name', f'Subnet{netuid}')
                }
        
        logger.info(f"✓ Got data for {len(subnet_data)} subnets")
        return subnet_data
        
    except Exception as e:
        logger.error(f"Failed: {e}")
        return {}


def get_current_block() -> int:
    """Get current block number."""
    try:
        import bittensor as bt
        subtensor = bt.subtensor(network=NETWORK)
        return subtensor.get_current_block()
    except Exception as e:
        logger.error(f"Failed to get block: {e}")
        return 0


def fetch_price_at_block(netuid: int, block: int, subtensor) -> float:
    """Fetch alpha price at specific block using the official SDK method."""
    try:
        balance = subtensor.get_subnet_price(netuid=netuid, block=block)
        price_value = float(balance.tao)
        return price_value if price_value > 0 else None
    except Exception as e:
        logger.debug(f"Failed to fetch price for subnet {netuid} at block {block}: {e}")
        return None


def run_backtest(start_date: datetime, end_date: datetime):
    """Run backtest with actual weights and live data."""
    logger.info("=" * 80)
    logger.info("TAO20 REAL BACKTEST (Feb 27 - Oct 27, 2025)")
    logger.info("=" * 80)
    logger.info("")
    
    # Get subnet data for APY
    subnet_data = get_subnet_data()
    if not subnet_data:
        logger.error("Failed to get subnet data")
        return
    
    # Get current block and calculate start block
    current_block = get_current_block()
    if current_block == 0:
        logger.error("Failed to get current block")
        return
    
    days_to_backtest = (end_date - start_date).days
    start_block = current_block - (days_to_backtest * BLOCKS_PER_DAY)
    
    logger.info(f"Backtesting {days_to_backtest} days ({start_date.strftime('%b %d')} to {end_date.strftime('%b %d, %Y')})")
    logger.info(f"Block range: {start_block} to {current_block}")
    logger.info("")
    
    # Connect to archive node
    import bittensor as bt
    logger.info(f"Connecting to archive node...")
    subtensor = bt.subtensor(network=NETWORK, archive_endpoints=[ARCHIVE_NODE])
    
    # Initialize with weight schedule (date = start of period when weights become active)
    weight_schedule = [
        (datetime(2025, 2, 27), FEB_27_WEIGHTS),   # Period 1: Feb 27
        (datetime(2025, 2, 28), MAR_13_WEIGHTS),   # Period 2: Feb 28 - Mar 13
        (datetime(2025, 3, 14), MAR_27_WEIGHTS),   # Period 3: Mar 14 - Mar 27
        (datetime(2025, 3, 28), APR_10_WEIGHTS),   # Period 4: Mar 28 - Apr 10
        (datetime(2025, 4, 11), APR_24_WEIGHTS),   # Period 5: Apr 11 - Apr 24
        (datetime(2025, 4, 25), MAY_08_WEIGHTS),   # Period 6: Apr 25 - May 08
        (datetime(2025, 5, 9), MAY_22_WEIGHTS),    # Period 7: May 09 - May 22
        (datetime(2025, 5, 23), JUN_05_WEIGHTS),   # Period 8: May 23 - Jun 05
        (datetime(2025, 6, 6), JUN_19_WEIGHTS),    # Period 9: Jun 06 - Jun 19
        (datetime(2025, 6, 20), JUL_03_WEIGHTS),   # Period 10: Jun 20 - Jul 03
        (datetime(2025, 7, 4), JUL_17_WEIGHTS),    # Period 11: Jul 04 - Jul 17
        (datetime(2025, 7, 18), JUL_31_WEIGHTS),   # Period 12: Jul 18 - Jul 31
        (datetime(2025, 8, 1), AUG_14_WEIGHTS),    # Period 13: Aug 01 - Aug 14
        (datetime(2025, 8, 15), AUG_28_WEIGHTS),   # Period 14: Aug 15 - Aug 28
        (datetime(2025, 8, 29), SEP_11_WEIGHTS),   # Period 15: Aug 29 - Sep 11
        (datetime(2025, 9, 12), SEP_25_WEIGHTS),   # Period 16: Sep 12 - Sep 25
        (datetime(2025, 9, 26), OCT_09_WEIGHTS),   # Period 17: Sep 26 - Oct 09
        (datetime(2025, 10, 10), OCT_23_WEIGHTS),  # Period 18: Oct 10 - Oct 23
    ]
    
    # Initialize
    nav = START_NAV
    price_only_nav = START_NAV
    weights = FEB_27_WEIGHTS.copy()
    current_weight_index = 0
    
    results = []
    
    logger.info(f"Starting backtest with {len(weights)} subnets in initial portfolio")
    logger.info("")
    
    for day in range(days_to_backtest + 1):
        current_date = start_date + timedelta(days=day)
        current_block_num = start_block + (day * BLOCKS_PER_DAY)
        
        # Check for rebalancing
        if current_weight_index < len(weight_schedule) - 1:
            next_rebalance_date, next_weights = weight_schedule[current_weight_index + 1]
            if current_date >= next_rebalance_date:
                # Check for new subnets being introduced
                old_subnets = set(weights.keys())
                new_subnets = set(next_weights.keys())
                introduced = new_subnets - old_subnets
                removed = old_subnets - new_subnets
                
                logger.info(f"🔄 REBALANCING on {current_date.strftime('%Y-%m-%d')} - NAV stays at {nav:.4f}")
                if introduced:
                    intro_weights = {n: next_weights[n] for n in introduced}
                    logger.info(f"   📥 Adding subnets: {intro_weights}")
                if removed:
                    logger.info(f"   📤 Removing subnets: {list(removed)}")
                
                weights = next_weights.copy()
                current_weight_index += 1
        
        # Fetch prices only for subnets in current portfolio
        day_prices = {}
        missing_prices = []
        for netuid in weights.keys():
            price = fetch_price_at_block(netuid, current_block_num, subtensor)
            if price:
                day_prices[netuid] = price
            else:
                missing_prices.append(netuid)
        
        # Log if we're missing critical price data
        if missing_prices and day % 10 == 0:
            total_missing_weight = sum(weights[n] for n in missing_prices)
            if total_missing_weight > 0.01:  # More than 1% missing
                logger.warning(f"Day {day}: Missing prices for subnets {missing_prices} (total weight: {total_missing_weight*100:.1f}%)")
        
        # Calculate returns with detailed tracking
        price_return = 0.0
        apy_return = 0.0
        subnet_details = {}
        
        if day > 0:  # Need previous prices for price return
            prev_prices = results[-1]['prices']
            
            # Calculate returns ONLY for subnets that have valid price data
            total_weight_with_prices = 0.0
            weighted_price_return = 0.0
            
            for netuid, weight in weights.items():
                subnet_price_return = 0.0
                subnet_apy_return = 0.0
                
                # Price return - only if we have both current and previous prices
                if netuid in day_prices and netuid in prev_prices:
                    if prev_prices[netuid] > 0 and day_prices[netuid] > 0:
                        price_change = (day_prices[netuid] - prev_prices[netuid]) / prev_prices[netuid]
                        subnet_price_return = price_change
                        weighted_price_return += weight * price_change
                        total_weight_with_prices += weight
                elif netuid in day_prices and netuid not in prev_prices:
                    # New subnet introduced during rebalancing - no price return on first day
                    # This is correct: we establish the position, no gain/loss yet
                    pass
                
                # APY return (daily) - calculated for all subnets with data
                if netuid in subnet_data:
                    daily_yield = (subnet_data[netuid]['alpha_apy'] / 100) / 365
                    subnet_apy_return = daily_yield
                    apy_return += weight * daily_yield
                
                if netuid in day_prices:
                    subnet_details[netuid] = {
                        'price': day_prices[netuid],
                        'price_return': subnet_price_return,
                        'apy_return': subnet_apy_return,
                        'weight': weight,
                        'apy': subnet_data.get(netuid, {}).get('alpha_apy', 0)
                    }
            
            # Normalize price return by actual weight coverage
            if total_weight_with_prices > 0:
                price_return = weighted_price_return
            else:
                price_return = 0.0
        else:
            # First day - only APY, establish prices
            for netuid, weight in weights.items():
                if netuid in subnet_data:
                    daily_yield = (subnet_data[netuid]['alpha_apy'] / 100) / 365
                    apy_return += weight * daily_yield
                
                if netuid in day_prices:
                    subnet_details[netuid] = {
                        'price': day_prices[netuid],
                        'price_return': 0.0,
                        'apy_return': subnet_data.get(netuid, {}).get('alpha_apy', 0) / 100 / 365,
                        'weight': weight,
                        'apy': subnet_data.get(netuid, {}).get('alpha_apy', 0)
                    }
        
        # Update NAV
        nav *= (1 + price_return + apy_return)
        price_only_nav *= (1 + price_return)
        
        results.append({
            'date': current_date,
            'nav': nav,
            'price_only_nav': price_only_nav,
            'price_return': price_return,
            'apy_return': apy_return,
            'total_return': price_return + apy_return,
            'prices': day_prices.copy(),
            'subnet_details': subnet_details
        })
        
        # Log progress with details
        if day % 5 == 0 or day < 3:
            logger.info(
                f"Day {day:2d} ({current_date.strftime('%Y-%m-%d')}): "
                f"NAV={nav:.4f}, Price Ret={price_return*100:+.3f}%, "
                f"APY Ret={apy_return*100:+.3f}%, Total={(price_return+apy_return)*100:+.3f}%"
            )
    
    logger.info("")
    logger.info("✓ Backtest complete!")
    logger.info("")
    
    # Create DataFrame
    df = pd.DataFrame([{
        'date': r['date'],
        'nav': r['nav'],
        'price_only_nav': r['price_only_nav'],
        'price_return': r['price_return'],
        'apy_return': r['apy_return'],
        'total_return': r['total_return']
    } for r in results])
    
    # Statistics
    final_nav = df.iloc[-1]['nav']
    total_return = (final_nav - START_NAV) / START_NAV * 100
    days_passed = len(df) - 1
    annualized = ((final_nav / START_NAV) ** (365 / days_passed) - 1) * 100 if days_passed > 0 else 0
    
    # Calculate price vs APY breakdown
    total_price_return = (df.iloc[-1]['price_only_nav'] - START_NAV) / START_NAV * 100
    total_apy_contribution = total_return - total_price_return
    
    logger.info("=" * 80)
    logger.info("RESULTS")
    logger.info("=" * 80)
    logger.info(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} ({days_passed} days)")
    logger.info(f"Starting NAV: {START_NAV:.4f}")
    logger.info(f"Ending NAV: {final_nav:.4f}")
    logger.info(f"Price-Only NAV: {df.iloc[-1]['price_only_nav']:.4f}")
    logger.info("")
    logger.info(f"Total Return: {total_return:.2f}%")
    logger.info(f"  ├─ Price Return: {total_price_return:.2f}%")
    logger.info(f"  └─ APY Contribution: {total_apy_contribution:.2f}%")
    logger.info(f"Annualized Return: {annualized:.2f}%")
    logger.info("")
    
    # Show some subnet details from last day
    if 'subnet_details' in results[-1]:
        logger.info("Sample Subnet Performance (Last Day):")
        last_details = results[-1]['subnet_details']
        sorted_subnets = sorted(last_details.items(), key=lambda x: x[1]['weight'], reverse=True)[:5]
        for netuid, details in sorted_subnets:
            logger.info(
                f"  Subnet {netuid:3d}: Price={details['price']:.6f} TAO/alpha, "
                f"APY={details['apy']:.1f}%, Weight={details['weight']*100:.1f}%"
            )
        logger.info("")
    
    # Save
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs('backtest_results', exist_ok=True)
    
    csv_file = f"backtest_results/tao20_real_backtest_{timestamp}.csv"
    df.to_csv(csv_file, index=False)
    logger.info(f"✓ Saved: {csv_file}")
    
    # Also save detailed subnet-by-subnet prices
    price_detail_data = []
    for r in results:
        # Find the applicable weight for this date
        applicable_weights = FEB_27_WEIGHTS
        for rebal_date, rebal_weights in weight_schedule:
            if r['date'] >= rebal_date:
                applicable_weights = rebal_weights
            else:
                break
        
        for netuid, price in r['prices'].items():
            price_detail_data.append({
                'date': r['date'],
                'netuid': netuid,
                'price': price,
                'weight': applicable_weights.get(netuid, 0)
            })
    
    if price_detail_data:
        price_detail_df = pd.DataFrame(price_detail_data)
        detail_file = f"backtest_results/tao20_subnet_prices_{timestamp}.csv"
        price_detail_df.to_csv(detail_file, index=False)
        logger.info(f"✓ Saved detailed prices: {detail_file}")
    
    # Plot with 3 subplots
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(16, 14))
    
    # NAV plot
    ax1.plot(df['date'], df['nav'], 'b-', linewidth=2.5, label='Total NAV (Price + APY)')
    ax1.plot(df['date'], df['price_only_nav'], 'r--', linewidth=1.5, label='Price Only NAV')
    ax1.axhline(y=START_NAV, color='gray', linestyle=':', alpha=0.5, label='Starting NAV')
    
    # Add rebalance dates as vertical lines (skip first date as it's the start)
    for i, (rebal_date, _) in enumerate(weight_schedule[1:], 1):
        if i == 1:
            ax1.axvline(x=rebal_date, color='green', alpha=0.3, linestyle='--', linewidth=1, label='Rebalances')
        else:
            ax1.axvline(x=rebal_date, color='green', alpha=0.3, linestyle='--', linewidth=1)
    
    ax1.set_xlabel('Date', fontsize=11)
    ax1.set_ylabel('NAV', fontsize=11)
    ax1.set_title('TAO20 Real Backtest: Feb 27 - Oct 27, 2025 (Actual Historical Weights)', fontsize=14, fontweight='bold')
    ax1.legend(loc='best', fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=9)
    
    # Daily returns breakdown (stacked)
    ax2.bar(df['date'], df['price_return']*100, color='coral', alpha=0.7, label='Price Return')
    ax2.bar(df['date'], df['apy_return']*100, bottom=df['price_return']*100, color='lightblue', alpha=0.7, label='APY Return')
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    
    # Add rebalance dates
    for rebal_date, _ in weight_schedule[1:]:
        ax2.axvline(x=rebal_date, color='green', alpha=0.2, linestyle='--', linewidth=1)
    ax2.set_xlabel('Date', fontsize=11)
    ax2.set_ylabel('Daily Return (%)', fontsize=11)
    ax2.set_title('Daily Returns Breakdown (Price vs APY)', fontsize=12, fontweight='bold')
    ax2.legend(loc='best', fontsize=9)
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=9)
    
    # Cumulative returns comparison
    df['cumulative_price'] = ((df['price_only_nav'] / START_NAV) - 1) * 100
    df['cumulative_apy'] = ((df['nav'] / df['price_only_nav']) - 1) * 100
    
    ax3.fill_between(df['date'], 0, df['cumulative_price'], color='coral', alpha=0.5, label='Price Contribution')
    ax3.fill_between(df['date'], df['cumulative_price'], df['cumulative_price'] + df['cumulative_apy'], 
                     color='lightblue', alpha=0.5, label='APY Contribution')
    ax3.plot(df['date'], df['cumulative_price'] + df['cumulative_apy'], 'b-', linewidth=2, label='Total Return')
    ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    
    # Add rebalance dates
    for rebal_date, _ in weight_schedule[1:]:
        ax3.axvline(x=rebal_date, color='green', alpha=0.2, linestyle='--', linewidth=1)
    ax3.set_xlabel('Date', fontsize=11)
    ax3.set_ylabel('Cumulative Return (%)', fontsize=11)
    ax3.set_title('Cumulative Return Attribution', fontsize=12, fontweight='bold')
    ax3.legend(loc='best', fontsize=9)
    ax3.grid(True, alpha=0.3)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=9)
    
    plt.tight_layout()
    
    plot_file = f"backtest_results/tao20_real_backtest_{timestamp}.png"
    plt.savefig(plot_file, dpi=150, bbox_inches='tight')
    logger.info(f"✓ Plot saved: {plot_file}")
    logger.info("")
    
    # Open plot
    os.system(f"open {plot_file}")
    
    return df


if __name__ == '__main__':
    start = datetime(2025, 2, 27)  # First TAO20 weighting date
    end = datetime.now()
    
    run_backtest(start, end)

