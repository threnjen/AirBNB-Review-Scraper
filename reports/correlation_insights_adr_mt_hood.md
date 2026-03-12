# Average Daily Rate Correlation Analysis

**Search Zone:** mt_hood

**Size Adjustment:** XGBoost regression on capacity, bedrooms, beds, bathrooms, BEDS_PER_PERSON, BATHS_PER_PERSON, BEDROOMS_PER_PERSON, DIST_TO_POI (R² = 0.747)

**High Tier Residual:** +42.98 (top 25%, n=207)

**Low Tier Residual:** -53.10 (bottom 25%, n=207)

---

# Analysis of Mt. Hood Airbnb Properties: Drivers of Higher Size-Adjusted Nightly Rates (ADR)

---

## 1. Key Differentiators

The following features most strongly distinguish properties earning **more than their size predicts** (High Residual Tier) compared to those earning less (Low Residual Tier), based on percentage point differences in amenity prevalence:

| Feature       | High Residual % | Low Residual % | Difference (pp) |
|---------------|-----------------|----------------|-----------------|
| Jacuzzi       | 67.6%           | 33.3%          | +34.3%          |
| Ocean View    | 38.6%           | 15.0%          | +23.7%          |
| Firepit       | 59.4%           | 44.9%          | +14.5%          |
| Grill         | 82.6%           | 69.1%          | +13.5%          |
| Dishwasher    | 86.5%           | 74.4%          | +12.1%          |
| Snowflake (likely seasonal/holiday decor) | 60.4% | 49.8% | +10.6%          |
| Fireplace     | 75.4%           | 65.7%          | +9.7%           |

**Summary:**  
The presence of **Jacuzzis, ocean views, and outdoor amenities like firepits and grills** are the strongest differentiators. Indoor conveniences such as dishwashers and fireplaces also contribute meaningfully.

---

## 2. Luxury Amenity Patterns

Amenities that correlate with earning a premium beyond size include:

- **Hot Tubs/Jacuzzis:** Present in 67.6% of high residual vs. 33.3% low residual (+34.3%)  
- **Views (Ocean):** 38.6% vs. 15.0% (+23.7%)  
- **Firepits:** 59.4% vs. 44.9% (+14.5%)  
- **Game Rooms (e.g., Pool Table):** 7.2% vs. 2.4% (+4.8%)  
- **Saunas:** 15.5% vs. 10.1% (+5.3%)  
- **Outdoor Entertainment (Grill, Outdoor TV):** Grill 82.6% vs. 69.1% (+13.5%)  
- **EV Chargers:** 11.1% vs. 6.3% (+4.8%)  

**Insight:**  
Properties with **luxury relaxation features (hot tubs, saunas), scenic views, and enhanced outdoor entertainment options** command higher premiums, indicating guests highly value experiential and comfort-oriented amenities beyond basic lodging.

---

## 3. Per-Person Ratios

| Ratio               | High Residual Avg | Low Residual Avg | Difference  |
|---------------------|-------------------|------------------|-------------|
| Beds Per Person     | 0.61              | 0.63             | -0.02       |
| Baths Per Person    | 0.23              | 0.24             | -0.01       |
| Bedrooms Per Person | 0.36              | 0.36             | +0.01       |

**Interpretation:**  
- Ratios are **nearly identical** between high and low residual groups, with minimal differences.  
- This suggests that **space allocation per guest (beds, baths, bedrooms per person) is not a key driver** of premium pricing beyond size.  
- Instead, **amenity quality and experience** appear more important than simply offering more space per guest.

---

## 4. Pet Policy Impact

- The data does **not explicitly provide pet policy prevalence** in the high vs. low residual tiers.  
- However, sample descriptions indicate **pets are allowed in some low residual properties** (e.g., Property 8785570).  
- Premium listings emphasize luxury amenities and experiences rather than pet-friendliness.  

**Conclusion:**  
There is **no clear evidence that allowing pets correlates with higher size-adjusted ADR** in this Mt. Hood market. Pet-friendly policies may be neutral or slightly associated with lower premiums, but more data would be needed for confirmation.

---

## 5. Description Language Patterns

**High Residual Properties:**

- Emphasize **luxury, exclusivity, and unique experiences** (e.g., "stunning mountain views," "chef’s kitchen," "private hot tub," "sauna," "game room").  
- Highlight **large group accommodations** and **multiple entertainment options** (pool tables, firepits, outdoor TVs).  
- Use evocative, experience-focused language: "relaxation at its finest," "create lasting memories," "luxury ski and biking paradise."  
- Reference **media features and accolades** ("Featured on TV series," "Travel Channel").  
- Stress **scenic location and privacy** ("set on three serene acres," "waterfront lodge").

**Low Residual Properties:**

- More functional and factual tone: "3 large bedroom suites," "kitchen with refrigerator," "spacious family room."  
- Focus on **basic amenities and proximity to activities** rather than luxury or exclusivity.  
- Less emphasis on unique experiences or premium features.  
- Mention pet policies and practical details more often.

---

## 6. Recommendations for Hosts

To increase nightly rates beyond what property size alone would predict, Mt. Hood hosts should:

1. **Invest in High-Value Luxury Amenities:**  
   Add or highlight **hot tubs/jacuzzis, saunas, and fireplaces** to enhance guest relaxation and appeal.

2. **Capitalize on Views and Outdoor Spaces:**  
   Promote or create **scenic views (especially ocean or mountain), firepits, grills, and outdoor entertainment setups** like TVs or game pits.

3. **Create Unique Guest Experiences:**  
   Incorporate **game rooms (pool tables), chef’s kitchens, and multi-functional social spaces** to attract larger groups seeking memorable stays.

4. **Use Engaging, Experience-Focused Descriptions:**  
   Craft listings that emphasize **luxury, exclusivity, and memorable moments**, referencing any media features or unique property stories.

5. **Enhance Convenience and Modern Comforts:**  
   Ensure amenities like **dishwashers, washers/dryers, and EV chargers** are available and clearly communicated to guests.

---

# Summary

In Mt. Hood’s Airbnb market, **premium pricing beyond size is driven primarily by luxury amenities, scenic views, and experiential offerings rather than additional space per guest or pet policies.** Hosts aiming to boost their ADR should focus on creating a high-end, memorable guest experience with standout features like hot tubs, firepits, and game rooms, paired with compelling, evocative listing descriptions.