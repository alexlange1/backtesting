#!/usr/bin/env python3
"""
TAO20 Real Historical Backtest - Using Local Price Data
========================================================
Uses actual TAO20 portfolio weights and daily price data from emissions_v2 folder.
Includes APY/dividend calculations for complete return attribution.

Author: Alexander Lange
Date: October 27, 2025
"""

import os
import json
import glob
import logging
import math
import re
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

NETWORK = 'finney'
START_NAV = 1.0

# APY Model
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
    64: 0.19256152994837228,
    14: 0.10031716637787322,
    56: 0.08392180095032617,
    4: 0.0800902100238625,
    3: 0.07896569862740782,
    51: 0.06652660777271495,
    8: 0.048618177176007256,
    5: 0.0426034849713084,
    9: 0.03739911457307092,
    19: 0.03674644538506796,
    1: 0.028821459021521206,
    68: 0.02698512816651934,
    17: 0.026853405965773913,
    44: 0.0250168657360174,
    13: 0.024601345221269104,
    34: 0.024319517923850998,
    10: 0.02275534306272607,
    81: 0.01831436276228483,
    33: 0.01794506673993246,
    75: 0.016637269594093142,
}

# Period 9: 20250606 to 20250619
JUN_19_WEIGHTS = {
    64: 0.20176719783709682,
    14: 0.08494679907485252,
    3: 0.0839293781811753,
    4: 0.0780814702491575,
    56: 0.07716182716924162,
    51: 0.07277851283533308,
    5: 0.05198107396791463,
    8: 0.04992356184558744,
    9: 0.03913626059306385,
    19: 0.03402428145363197,
    17: 0.029168774354212765,
    44: 0.02839194794879724,
    68: 0.026621891968133714,
    13: 0.025832394701348484,
    1: 0.02509355252866133,
    34: 0.02380467858264988,
    10: 0.017715653770338704,
    33: 0.01711872654253833,
    77: 0.016545423800183933,
    75: 0.015976592596080915,
}

# Period 10: 20250620 to 20250703
JUL_03_WEIGHTS = {
    64: 0.195961979258833,
    51: 0.0856115834620603,
    3: 0.08212614803212683,
    4: 0.07967988303252449,
    56: 0.07311586297506088,
    8: 0.054980731776137916,
    5: 0.051814254405138156,
    14: 0.045948495804894025,
    44: 0.04005790962239768,
    9: 0.03974524209591033,
    19: 0.03450981157810419,
    17: 0.03092476046879039,
    1: 0.028603697620931928,
    34: 0.028355687642109495,
    13: 0.027169855067407354,
    68: 0.024790344853111455,
    33: 0.021434096712063665,
    39: 0.019366091331887072,
    63: 0.01840895217707025,
    10: 0.01739461208344055,
}

# Period 11: 20250704 to 20250717
JUL_17_WEIGHTS = {
    64: 0.18511518818775535,
    51: 0.10286646354151367,
    4: 0.07744616441118739,
    3: 0.07594365285861568,
    56: 0.06966910406745962,
    8: 0.05746705295324976,
    5: 0.042207425918859995,
    44: 0.041743092217704655,
    9: 0.03865690086726219,
    14: 0.034751050136880055,
    17: 0.033974598575596274,
    34: 0.03106211338797137,
    33: 0.030415179355672752,
    19: 0.028728715868316573,
    39: 0.028573462573269634,
    1: 0.028162888268564182,
    68: 0.026082763220541004,
    13: 0.02605549085284127,
    63: 0.02345271731865402,
    12: 0.017625975418084496,
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


def get_subnet_data() -> Dict[int, Dict]:
    """Fetch current subnet data for APY calculation."""
    logger.info("Fetching subnet data for APY calculations...")
    
    try:
        cmd = ['btcli', 'subnets', 'list', '--network', NETWORK, '--json-output']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            logger.warning("Failed to fetch subnet data, APY will be excluded")
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
        
        logger.info(f"✓ Got APY data for {len(subnet_data)} subnets")
        return subnet_data
        
    except Exception as e:
        logger.warning(f"Failed to get subnet data: {e}. APY will be excluded from backtest.")
        return {}


def load_price_data(data_dir: str = 'data/emissions_v2') -> Dict[str, Dict[int, float]]:
    """
    Load daily price data from emissions_v2 JSON files.
    
    Returns:
        Dict mapping date string (YYYYMMDD) to dict of {subnet_id: price}
    """
    logger.info("Loading price data from emissions_v2 files...")
    
    files = sorted(glob.glob(f'{data_dir}/emissions_v2_*.json'))
    price_data = {}
    
    for filepath in files:
        # Extract date from filename: emissions_v2_20250227.json -> 20250227
        filename = os.path.basename(filepath)
        date_str = filename.replace('emissions_v2_', '').replace('.json', '')
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # The "emissions" field actually contains prices (TAO/alpha)
            prices = data.get('emissions', {})
            
            # Convert string keys to integers
            price_dict = {int(netuid): float(price) for netuid, price in prices.items()}
            price_data[date_str] = price_dict
            
        except Exception as e:
            logger.warning(f"Failed to load {filepath}: {e}")
            continue
    
    logger.info(f"✓ Loaded price data for {len(price_data)} days")
    logger.info(f"  Date range: {min(price_data.keys())} to {max(price_data.keys())}")
    
    return price_data


def run_backtest(start_date: datetime, end_date: datetime):
    """Run backtest with actual weights and price data."""
    logger.info("=" * 80)
    logger.info("TAO20 REAL BACKTEST (Feb 27 - Oct 26, 2025)")
    logger.info("=" * 80)
    logger.info("")
    
    # Get subnet data for APY
    subnet_data = get_subnet_data()
    
    # Load all price data
    price_data = load_price_data()
    
    # Weight schedule (date = start of period when weights become active)
    weight_schedule = [
        (datetime(2025, 2, 27), FEB_27_WEIGHTS),
        (datetime(2025, 2, 28), MAR_13_WEIGHTS),
        (datetime(2025, 3, 14), MAR_27_WEIGHTS),
        (datetime(2025, 3, 28), APR_10_WEIGHTS),
        (datetime(2025, 4, 11), APR_24_WEIGHTS),
        (datetime(2025, 4, 25), MAY_08_WEIGHTS),
        (datetime(2025, 5, 9), MAY_22_WEIGHTS),
        (datetime(2025, 5, 23), JUN_05_WEIGHTS),
        (datetime(2025, 6, 6), JUN_19_WEIGHTS),
        (datetime(2025, 6, 20), JUL_03_WEIGHTS),
        (datetime(2025, 7, 4), JUL_17_WEIGHTS),
        (datetime(2025, 7, 18), JUL_31_WEIGHTS),
        (datetime(2025, 8, 1), AUG_14_WEIGHTS),
        (datetime(2025, 8, 15), AUG_28_WEIGHTS),
        (datetime(2025, 8, 29), SEP_11_WEIGHTS),
        (datetime(2025, 9, 12), SEP_25_WEIGHTS),
        (datetime(2025, 9, 26), OCT_09_WEIGHTS),
        (datetime(2025, 10, 10), OCT_23_WEIGHTS),
    ]
    
    # Initialize
    nav = START_NAV
    price_only_nav = START_NAV
    weights = FEB_27_WEIGHTS.copy()
    current_weight_index = 0
    
    results = []
    days_to_backtest = (end_date - start_date).days
    
    logger.info(f"Backtesting {days_to_backtest} days")
    logger.info(f"Starting with {len(weights)} subnets in portfolio")
    if subnet_data:
        logger.info(f"APY data available for {len(subnet_data)} subnets")
    else:
        logger.info("APY data not available - backtest will use price returns only")
    logger.info("")
    
    for day in range(days_to_backtest + 1):
        current_date = start_date + timedelta(days=day)
        date_str = current_date.strftime('%Y%m%d')
        
        # Get prices for this day
        day_prices = price_data.get(date_str, {})
        
        if not day_prices:
            logger.warning(f"No price data for {date_str}, skipping day")
            continue
        
        # Calculate returns USING CURRENT WEIGHTS (before any rebalancing)
        price_return = 0.0
        apy_return = 0.0
        
        if day > 0 and results:
            prev_prices = results[-1]['prices']
            
            # Calculate weighted price return and APY return
            total_weight_with_prices = 0.0
            
            for netuid, weight in weights.items():
                # Price return
                if netuid in day_prices and netuid in prev_prices:
                    if prev_prices[netuid] > 0 and day_prices[netuid] > 0:
                        price_change = (day_prices[netuid] - prev_prices[netuid]) / prev_prices[netuid]
                        price_return += weight * price_change
                        total_weight_with_prices += weight
                elif netuid in day_prices and netuid not in prev_prices:
                    # New subnet - no price return on first day
                    total_weight_with_prices += weight
                
                # APY return (daily yield)
                if netuid in subnet_data:
                    daily_yield = (subnet_data[netuid]['alpha_apy'] / 100) / 365
                    apy_return += weight * daily_yield
            
            # Track missing weight
            if total_weight_with_prices < 0.99:
                missing_weight = 1.0 - total_weight_with_prices
                logger.warning(f"Day {day}: Missing {missing_weight*100:.1f}% of portfolio weight")
        else:
            # First day - only APY (establish baseline prices)
            for netuid, weight in weights.items():
                if netuid in subnet_data:
                    daily_yield = (subnet_data[netuid]['alpha_apy'] / 100) / 365
                    apy_return += weight * daily_yield
        
        # Update NAVs with returns from current holdings
        nav *= (1 + price_return + apy_return)
        price_only_nav *= (1 + price_return)
        
        # Save results with CURRENT weights/prices
        results.append({
            'date': current_date,
            'nav': nav,
            'price_only_nav': price_only_nav,
            'price_return': price_return,
            'apy_return': apy_return,
            'prices': {n: day_prices.get(n, 0) for n in weights.keys()}
        })
        
        # NOW check for rebalancing (AFTER calculating returns and updating NAV)
        if current_weight_index < len(weight_schedule) - 1:
            next_rebalance_date, next_weights = weight_schedule[current_weight_index + 1]
            if current_date >= next_rebalance_date:
                old_subnets = set(weights.keys())
                new_subnets = set(next_weights.keys())
                introduced = new_subnets - old_subnets
                removed = old_subnets - new_subnets
                
                logger.info(f"🔄 REBALANCING on {current_date.strftime('%Y-%m-%d')} - NAV stays at {nav:.4f}")
                if introduced:
                    intro_weights = {n: next_weights[n] for n in introduced}
                    logger.info(f"   📥 Adding: {intro_weights}")
                if removed:
                    logger.info(f"   📤 Removing: {list(removed)}")
                
                weights = next_weights.copy()
                current_weight_index += 1
        
        # Log progress
        if day % 10 == 0 or day < 3:
            logger.info(
                f"Day {day:3d} ({current_date.strftime('%Y-%m-%d')}): "
                f"NAV={nav:.4f}, Price={price_return*100:+.2f}%, APY={apy_return*100:+.3f}%"
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
    
    # Save
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs('backtest_results', exist_ok=True)
    
    csv_file = f"backtest_results/tao20_backtest_{timestamp}.csv"
    df.to_csv(csv_file, index=False)
    logger.info(f"✓ Saved: {csv_file}")
    
    # Plot with 3 subplots
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(16, 14))
    
    # NAV plot
    ax1.plot(df['date'], df['nav'], 'b-', linewidth=2.5, label='Total NAV (Price + APY)')
    ax1.plot(df['date'], df['price_only_nav'], 'r--', linewidth=1.5, label='Price Only NAV')
    ax1.axhline(y=START_NAV, color='gray', linestyle=':', alpha=0.5, label='Starting NAV')
    
    # Add rebalance dates
    for i, (rebal_date, _) in enumerate(weight_schedule[1:], 1):
        if i == 1:
            ax1.axvline(x=rebal_date, color='green', alpha=0.3, linestyle='--', linewidth=1, label='Rebalances')
        else:
            ax1.axvline(x=rebal_date, color='green', alpha=0.3, linestyle='--', linewidth=1)
    
    ax1.set_xlabel('Date', fontsize=11)
    ax1.set_ylabel('NAV', fontsize=11)
    ax1.set_title('TAO20 Real Backtest: Feb 27 - Oct 26, 2025 (Actual Historical Weights)', fontsize=14, fontweight='bold')
    ax1.legend(loc='best', fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=9)
    
    # Daily returns breakdown (stacked)
    ax2.bar(df['date'], df['price_return']*100, color='coral', alpha=0.7, label='Price Return')
    ax2.bar(df['date'], df['apy_return']*100, bottom=df['price_return']*100, color='lightblue', alpha=0.7, label='APY Return')
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    
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
    
    plot_file = f"backtest_results/tao20_backtest_{timestamp}.png"
    plt.savefig(plot_file, dpi=150, bbox_inches='tight')
    logger.info(f"✓ Plot saved: {plot_file}")
    logger.info("")
    
    # Open plot
    os.system(f"open {plot_file}")
    
    return df


if __name__ == '__main__':
    start = datetime(2025, 2, 27)
    end = datetime(2025, 10, 26)  # Last available data
    
    run_backtest(start, end)

