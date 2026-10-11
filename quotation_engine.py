"""
FloraFlow AI Botanical Quotation Engine
---------------------------------------
Expert rule-based botanical estimating system for nursery projects, green spaces,
and landscape installations. Calculates space capacity, ecological suitability,
catalog matching, pot pairings, material nutrition, and labor costs.
"""

from datetime import date, timedelta
import random
import json
from decimal import Decimal
from fpdf import FPDF


SPACE_CONFIGS = {
    'indoor': {
        'name': 'Indoor (Living / Bedroom / Office)',
        'density_sqft': 12,
        'min_plants': 3,
        'max_plants': 16,
        'categories': [1, 8, 10],  # Indoor Plants, Succulents, Herbs
        'light_default': 'partial'
    },
    'balcony': {
        'name': 'Balcony Garden',
        'density_sqft': 10,
        'min_plants': 4,
        'max_plants': 22,
        'categories': [1, 2, 3, 9, 10, 8],  # Indoor, Outdoor Ornamental, Seasonal, Climbers, Herbs, Succulents
        'light_default': 'partial'
    },
    'rooftop': {
        'name': 'Rooftop / Terrace Garden',
        'density_sqft': 16,
        'min_plants': 6,
        'max_plants': 30,
        'categories': [2, 7, 3, 4, 8],  # Outdoor, Palms, Seasonal, Fruit, Succulents
        'light_default': 'fullSun'
    },
    'backyard': {
        'name': 'Backyard / Garden Lawn',
        'density_sqft': 20,
        'min_plants': 8,
        'max_plants': 38,
        'categories': [2, 6, 7, 4, 5, 3],  # Outdoor, Hedges, Palms, Fruit, Trees, Seasonal
        'light_default': 'fullSun'
    },
    'commercial': {
        'name': 'Commercial (Cafe / Retail / Office Lobby)',
        'density_sqft': 15,
        'min_plants': 5,
        'max_plants': 25,
        'categories': [1, 7, 2],  # Indoor, Palms, Outdoor
        'light_default': 'partial'
    }
}


def calculate_quotation(cursor, form_data):
    """
    Core AI estimation algorithm.
    Reads current inventory from database and generates an optimized quotation.
    """
    customer_name = form_data.get('customerName', '').strip() or 'Valued Customer'
    customer_phone = form_data.get('customerPhone', '').strip() or '—'
    space_type = form_data.get('spaceType', 'balcony')
    if space_type not in SPACE_CONFIGS:
        space_type = 'balcony'

    try:
        area_sqft = int(form_data.get('areaSqFt', 100))
        area_sqft = max(10, min(area_sqft, 2500))
    except (ValueError, TypeError):
        area_sqft = 100

    sunlight = form_data.get('sunlight', 'partial')  # fullSun, partial, lowLight
    care_level = form_data.get('careLevel', 'low')   # low, moderate, high
    tier = form_data.get('tier', 'standard')         # economy, standard, premium

    include_soil = form_data.get('includeSoil') in ('on', 'true', True, '1', 1)
    include_pots = form_data.get('includePots') in ('on', 'true', True, '1', 1)
    include_tools = form_data.get('includeTools') in ('on', 'true', True, '1', 1)
    include_labor = form_data.get('includeLabor') in ('on', 'true', True, '1', 1)

    # 1. Calculate Target Plant Capacity
    cfg = SPACE_CONFIGS[space_type]
    base_count = round(area_sqft / cfg['density_sqft'])
    target_plant_count = max(cfg['min_plants'], min(base_count, cfg['max_plants']))

    # 2. Fetch In-Stock Plants
    cursor.execute("""
        SELECT p.plantId, p.plantName, p.categoryId, p.price, p.quantity, p.description, p.careInstructions,
               c.categoryName
        FROM Plants p
        LEFT JOIN PlantCategories c ON p.categoryId = c.categoryId
        WHERE p.quantity > 0
        ORDER BY p.price ASC
    """)
    available_plants = cursor.fetchall()

    # 3. Categorize & Score Plants for the Space
    valid_category_ids = set(cfg['categories'])

    # Light condition filtering
    if sunlight == 'lowLight':
        # Prioritize Category 1 (Indoor), deprioritize outdoor/full sun
        valid_category_ids = {1, 8, 9}
    elif sunlight == 'fullSun':
        # Prioritize outdoor, palms, fruit, seasonal flowering, succulents
        valid_category_ids = valid_category_ids - {1} or {2, 3, 7, 8, 6, 4}

    suitable_plants = [p for p in available_plants if p['categoryId'] in valid_category_ids]
    if not suitable_plants:
        # Fallback to any in-stock plants if specific categories are depleted
        suitable_plants = available_plants

    # Filter/Sort by Care Level
    hardy_keywords = ['hardy', 'snake', 'zz', 'money', 'palm', 'ficus', 'survives', 'tolerates', 'rubber']
    if care_level == 'low':
        # Sort plants matching hardy keywords to the top
        suitable_plants.sort(
            key=lambda x: (
                0 if any(k in (x['plantName'] + ' ' + (x['description'] or '')).lower() for k in hardy_keywords) else 1,
                float(x['price'])
            )
        )
    elif care_level == 'high':
        # Enthusiast: include flowering, delicate herbs, peace lily
        suitable_plants.sort(key=lambda x: float(x['price']), reverse=True)

    # Filter by Tier:
    # Economy prefers lower price items; Premium prefers architectural specimens
    if tier == 'economy':
        pool = sorted(suitable_plants, key=lambda x: float(x['price']))
    elif tier == 'premium':
        pool = sorted(suitable_plants, key=lambda x: float(x['price']), reverse=True)
    else:
        pool = list(suitable_plants)

    # 4. Allocate Selected Plants (Focal, Mid-Foliage, Accent)
    selected_plants = []
    allocated_count = 0
    pool_len = len(pool)

    # Determine unique plant varieties needed
    num_varieties = min(max(3, round(target_plant_count / 2)), pool_len)
    chosen_pool = pool[:num_varieties] if pool_len > 0 else []

    if chosen_pool:
        # Distribute target_plant_count among chosen varieties
        base_qty = target_plant_count // len(chosen_pool)
        remainder = target_plant_count % len(chosen_pool)

        for i, plant in enumerate(chosen_pool):
            qty = base_qty + (1 if i < remainder else 0)
            if qty > plant['quantity']:
                qty = plant['quantity']  # Clamp to available stock
            if qty <= 0:
                continue

            unit_price = float(plant['price'])
            subtotal = unit_price * qty

            # Assign an ecological role
            if i == 0 and unit_price > 1000:
                role = "Centerpiece Specimen (Focal)"
            elif i % 2 == 0:
                role = "Structural Foliage (Mid-Layer)"
            else:
                role = "Accent / Textural Filler"

            selected_plants.append({
                'id': plant['plantId'],
                'name': plant['plantName'],
                'category': plant.get('categoryName', 'Plant'),
                'qty': qty,
                'unitPrice': unit_price,
                'subtotal': subtotal,
                'role': role,
                'care': plant.get('careInstructions') or plant.get('description') or 'Regular watering'
            })
            allocated_count += qty

    total_plants_cost = sum(p['subtotal'] for p in selected_plants)

    # 5. Allocate Accessories (Pots, Soil, Nutrition, Tools)
    cursor.execute("SELECT * FROM Accessories WHERE quantity > 0 ORDER BY price ASC")
    all_accessories = cursor.fetchall()
    acc_by_name = {a['accessoryName'].lower(): a for a in all_accessories}

    selected_accessories = []

    # Helper to pick accessory
    def pick_accessory(search_terms, fallback_keyword='pot'):
        for term in search_terms:
            for name, acc in acc_by_name.items():
                if term in name and acc['quantity'] > 0:
                    return acc
        for name, acc in acc_by_name.items():
            if fallback_keyword in name and acc['quantity'] > 0:
                return acc
        return None

    # (A) Pots / Planters (if requested)
    if include_pots and allocated_count > 0:
        if tier == 'economy':
            pot_item = pick_accessory(['plastic pot 10 inch', 'terracotta pot 8 inch', 'plastic pot'])
        elif tier == 'premium':
            pot_item = pick_accessory(['ceramic planter', 'cement planter', 'terracotta pot 12 inch'])
        else:
            pot_item = pick_accessory(['terracotta pot 12 inch', 'terracotta pot 8 inch', 'hanging basket'])

        if pot_item:
            pot_qty = allocated_count
            if pot_qty > pot_item['quantity']:
                pot_qty = pot_item['quantity']
            u_price = float(pot_item['price'])
            selected_accessories.append({
                'id': pot_item['accessoryId'],
                'name': pot_item['accessoryName'],
                'purpose': 'Matching Planters & Containers',
                'qty': pot_qty,
                'unitPrice': u_price,
                'subtotal': u_price * pot_qty
            })

    # (B) Potting Soil & Soil Conditioner (if requested)
    if include_soil and allocated_count > 0:
        soil_item = pick_accessory(['potting soil mix 10 kg', 'coco peat block', 'potting soil'])
        if soil_item:
            # 1 bag per 3 plants
            soil_bags = max(1, round(allocated_count / 3))
            soil_bags = min(soil_bags, soil_item['quantity'])
            u_price = float(soil_item['price'])
            selected_accessories.append({
                'id': soil_item['accessoryId'],
                'name': soil_item['accessoryName'],
                'purpose': 'Aerated Potting Medium',
                'qty': soil_bags,
                'unitPrice': u_price,
                'subtotal': u_price * soil_bags
            })

        # Organic Fertilizer / Nutrition for standard/premium
        if tier in ('standard', 'premium'):
            fert_item = pick_accessory(['vermicompost 5 kg', 'cow dung manure', 'npk 20-20-20'])
            if fert_item:
                fert_bags = max(1, round(allocated_count / 5))
                fert_bags = min(fert_bags, fert_item['quantity'])
                u_price = float(fert_item['price'])
                selected_accessories.append({
                    'id': fert_item['accessoryId'],
                    'name': fert_item['accessoryName'],
                    'purpose': 'Organic Root Nutrition',
                    'qty': fert_bags,
                    'unitPrice': u_price,
                    'subtotal': u_price * fert_bags
                })

    # (C) Gardening Tools & Protection (if requested or large area)
    if include_tools or (area_sqft >= 200 and tier == 'premium'):
        tool_item = pick_accessory(['watering can 10 l', 'garden sprayer', 'gardening gloves'])
        if tool_item:
            u_price = float(tool_item['price'])
            selected_accessories.append({
                'id': tool_item['accessoryId'],
                'name': tool_item['accessoryName'],
                'purpose': 'Maintenance & Irrigation Tool',
                'qty': 1,
                'unitPrice': u_price,
                'subtotal': u_price
            })

    total_accessories_cost = sum(a['subtotal'] for a in selected_accessories)

    # 6. Labor & Installation Fee (if requested)
    if include_labor and allocated_count > 0:
        # Base charge Rs. 500 + Rs. 150 per potted plant
        labor_cost = 500.0 + (allocated_count * 150.0)
    else:
        labor_cost = 0.0

    grand_total = total_plants_cost + total_accessories_cost + labor_cost

    # 7. Generate Botanical Advisory & Metadata
    today_str = date.today().strftime('%d %b %Y')
    valid_until = (date.today() + timedelta(days=14)).strftime('%d %b %Y')
    quote_number = f"FF-Q-{date.today().strftime('%y%m%d')}-{random.randint(1000, 9999)}"

    # Advisory generation
    if sunlight == 'lowLight':
        water_schedule = "Every 8-12 days (allow top 2 inches of soil to completely dry)"
        light_advice = "Thrives in indirect or filtered light. Keep away from harsh midday windows."
    elif sunlight == 'fullSun':
        water_schedule = "Every 1-2 days during warm months; check moisture daily in direct sun"
        light_advice = "Direct sunlight ensures vigorous flowering and robust foliage growth."
    else:
        water_schedule = "Every 3-5 days when top layer feels dry to touch"
        light_advice = "Morning sunlight or bright ambient light provides optimal photosynthesis."

    if care_level == 'low':
        effort_mins = "15-20 mins / week"
    elif care_level == 'high':
        effort_mins = "45-60 mins / week"
    else:
        effort_mins = "25-35 mins / week"

    advisory = {
        'effort': effort_mins,
        'watering': water_schedule,
        'sunlight': light_advice,
        'nutrition': 'Feed organic compost or liquid fertilizer every 4 weeks during active growing season.',
        'co2Absorption': f"~{allocated_count * 12} kg CO2 / year estimated ecological contribution"
    }

    quote_data = {
        'quoteNumber': quote_number,
        'date': today_str,
        'validUntil': valid_until,
        'customerName': customer_name,
        'customerPhone': customer_phone,
        'spaceType': space_type,
        'spaceTypeName': cfg['name'],
        'areaSqFt': area_sqft,
        'sunlight': sunlight,
        'careLevel': care_level,
        'tier': tier,
        'includeSoil': include_soil,
        'includePots': include_pots,
        'includeTools': include_tools,
        'includeLabor': include_labor,
        'allocatedCount': allocated_count,
        'plants': selected_plants,
        'accessories': selected_accessories,
        'totalPlantsCost': total_plants_cost,
        'totalAccessoriesCost': total_accessories_cost,
        'laborCost': labor_cost,
        'grandTotal': grand_total,
        'advisory': advisory
    }

    return quote_data


def save_quotation_to_db(conn, quote_data, staff_id=None):
    """
    Saves generated quotation into the database Quotations table.
    """
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO Quotations (
            quoteNumber, customerName, customerPhone, spaceType, areaSqFt,
            sunlight, careLevel, tier, totalPlantsCost, totalAccessoriesCost,
            laborCost, grandTotal, quoteData, createdBy
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        quote_data['quoteNumber'],
        quote_data['customerName'],
        quote_data['customerPhone'],
        quote_data['spaceType'],
        quote_data['areaSqFt'],
        quote_data['sunlight'],
        quote_data['careLevel'],
        quote_data['tier'],
        Decimal(str(round(quote_data['totalPlantsCost'], 2))),
        Decimal(str(round(quote_data['totalAccessoriesCost'], 2))),
        Decimal(str(round(quote_data['laborCost'], 2))),
        Decimal(str(round(quote_data['grandTotal'], 2))),
        json.dumps(quote_data),
        staff_id
    ))
    conn.commit()
    return cursor.lastrowid


def build_quotation_pdf(quote_data):
    """
    Generates a clean, branded PDF quotation using fpdf2.
    """
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # --- Header Banner ---
    pdf.set_fill_color(27, 67, 50)  # Flora primary: #1b4332
    pdf.rect(0, 0, 210, 32, 'F')

    pdf.set_xy(15, 8)
    pdf.set_font('helvetica', 'B', 18)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, 'FLORAFLOW BOTANICAL NURSERY', new_x='LMARGIN', new_y='NEXT')

    pdf.set_xy(15, 17)
    pdf.set_font('helvetica', '', 9)
    pdf.set_text_color(216, 243, 220)
    pdf.cell(0, 5, 'AI GreenQuoter | Smart Botanical Project Estimate', new_x='LMARGIN', new_y='NEXT')

    # --- Meta Info Box ---
    pdf.set_y(38)
    pdf.set_text_color(40, 40, 40)
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(100, 6, f"Quotation: {quote_data['quoteNumber']}", ln=0)
    pdf.set_font('helvetica', '', 9)
    pdf.cell(80, 6, f"Date: {quote_data['date']} (Valid: {quote_data['validUntil']})", ln=1, align='R')

    pdf.set_font('helvetica', '', 9)
    pdf.cell(100, 5, f"Customer: {quote_data['customerName']} | Phone: {quote_data['customerPhone']}", ln=0)
    pdf.cell(80, 5, f"Space: {quote_data['spaceTypeName']} ({quote_data['areaSqFt']} sq ft)", ln=1, align='R')

    pdf.set_draw_color(200, 220, 210)
    pdf.line(15, 52, 195, 52)
    pdf.ln(5)

    # --- Plants Table ---
    pdf.set_font('helvetica', 'B', 11)
    pdf.set_text_color(27, 67, 50)
    pdf.cell(0, 7, f"1. Recommended Flora ({quote_data['allocatedCount']} Plants)", ln=1)

    # Table Header
    pdf.set_fill_color(240, 247, 242)
    pdf.set_text_color(27, 67, 50)
    pdf.set_font('helvetica', 'B', 8)
    pdf.cell(80, 7, 'Plant Name & Variety', border=1, fill=True)
    pdf.cell(40, 7, 'Ecological Role', border=1, fill=True)
    pdf.cell(15, 7, 'Qty', border=1, fill=True, align='C')
    pdf.cell(22, 7, 'Unit (Rs.)', border=1, fill=True, align='R')
    pdf.cell(23, 7, 'Subtotal', border=1, fill=True, align='R')
    pdf.ln()

    pdf.set_font('helvetica', '', 8)
    pdf.set_text_color(40, 40, 40)
    for p in quote_data['plants']:
        pdf.cell(80, 6, p['name'][:45], border='B')
        pdf.cell(40, 6, p['role'][:25], border='B')
        pdf.cell(15, 6, str(p['qty']), border='B', align='C')
        pdf.cell(22, 6, f"{p['unitPrice']:,.2f}", border='B', align='R')
        pdf.cell(23, 6, f"{p['subtotal']:,.2f}", border='B', align='R')
        pdf.ln()

    pdf.set_font('helvetica', 'B', 8)
    pdf.cell(157, 6, 'Plants Subtotal:', align='R')
    pdf.cell(23, 6, f"Rs. {quote_data['totalPlantsCost']:,.2f}", align='R')
    pdf.ln(7)

    # --- Accessories & Materials Table ---
    if quote_data['accessories']:
        pdf.set_font('helvetica', 'B', 11)
        pdf.set_text_color(27, 67, 50)
        pdf.cell(0, 7, '2. Planters, Soil & Growing Medium', ln=1)

        pdf.set_fill_color(240, 247, 242)
        pdf.set_font('helvetica', 'B', 8)
        pdf.cell(80, 7, 'Item Name', border=1, fill=True)
        pdf.cell(40, 7, 'Purpose', border=1, fill=True)
        pdf.cell(15, 7, 'Qty', border=1, fill=True, align='C')
        pdf.cell(22, 7, 'Unit (Rs.)', border=1, fill=True, align='R')
        pdf.cell(23, 7, 'Subtotal', border=1, fill=True, align='R')
        pdf.ln()

        pdf.set_font('helvetica', '', 8)
        pdf.set_text_color(40, 40, 40)
        for a in quote_data['accessories']:
            pdf.cell(80, 6, a['name'][:45], border='B')
            pdf.cell(40, 6, a['purpose'][:25], border='B')
            pdf.cell(15, 6, str(a['qty']), border='B', align='C')
            pdf.cell(22, 6, f"{a['unitPrice']:,.2f}", border='B', align='R')
            pdf.cell(23, 6, f"{a['subtotal']:,.2f}", border='B', align='R')
            pdf.ln()

        pdf.set_font('helvetica', 'B', 8)
        pdf.cell(157, 6, 'Accessories Subtotal:', align='R')
        pdf.cell(23, 6, f"Rs. {quote_data['totalAccessoriesCost']:,.2f}", align='R')
        pdf.ln(7)

    # --- Grand Total Box ---
    pdf.set_fill_color(244, 247, 245)
    pdf.rect(120, pdf.get_y(), 75, 26, 'F')
    curr_y = pdf.get_y() + 2

    pdf.set_xy(122, curr_y)
    pdf.set_font('helvetica', '', 8)
    pdf.cell(40, 4, 'Plants Subtotal:', ln=0)
    pdf.cell(30, 4, f"Rs. {quote_data['totalPlantsCost']:,.2f}", ln=1, align='R')

    pdf.set_x(122)
    pdf.cell(40, 4, 'Materials & Planters:', ln=0)
    pdf.cell(30, 4, f"Rs. {quote_data['totalAccessoriesCost']:,.2f}", ln=1, align='R')

    if quote_data['laborCost'] > 0:
        pdf.set_x(122)
        pdf.cell(40, 4, 'On-site Potting & Setup:', ln=0)
        pdf.cell(30, 4, f"Rs. {quote_data['laborCost']:,.2f}", ln=1, align='R')

    pdf.set_x(122)
    pdf.set_font('helvetica', 'B', 10)
    pdf.set_text_color(27, 67, 50)
    pdf.cell(40, 6, 'Estimated Total:', ln=0)
    pdf.cell(30, 6, f"Rs. {quote_data['grandTotal']:,.2f}", ln=1, align='R')

    pdf.set_y(curr_y + 22)
    pdf.ln(4)

    # --- AI Botanical Care Advisory Box ---
    adv = quote_data['advisory']
    pdf.set_fill_color(232, 245, 233)
    pdf.set_draw_color(64, 145, 108)
    pdf.rect(15, pdf.get_y(), 180, 24, 'DF')

    box_y = pdf.get_y() + 2
    pdf.set_xy(18, box_y)
    pdf.set_font('helvetica', 'B', 9)
    pdf.set_text_color(27, 67, 50)
    pdf.cell(0, 5, f"AI Botanical Care Guide ({adv['effort']})", ln=1)

    pdf.set_x(18)
    pdf.set_font('helvetica', '', 8)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(0, 4, f"- Watering: {adv['watering']}", ln=1)
    pdf.set_x(18)
    pdf.cell(0, 4, f"- Exposure: {adv['sunlight']}", ln=1)
    pdf.set_x(18)
    pdf.cell(0, 4, f"- Ecological Contribution: {adv['co2Absorption']}", ln=1)

    pdf.ln(6)

    # --- Footer ---
    pdf.set_font('helvetica', 'I', 7)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 4, 'This is an algorithmic project estimate generated by FloraFlow AI Engine. Prices subject to inventory availability.', ln=1, align='C')

    # Return PDF raw bytes
    return bytes(pdf.output())
