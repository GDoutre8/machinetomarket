"""QA harness for Listing Copy Engine v3 across 12+ machines."""
from dealer_input import DealerInput
from listing_builder import build_listing_text


def out(title, di, specs, eq, tone="dealer_clean"):
    print(f"\n{'='*72}\n{title}  [{eq} / {tone}]\n{'='*72}")
    print(build_listing_text(di, specs, equipment_type=eq, tone_profile=tone))


# 1. CTL — high flow, low hour
out("CTL Bobcat T770 (low hour, high flow)",
    DealerInput(year=2021, make="Bobcat", model="T770", hours=1193,
                cab_type="enclosed", heater=True, ac=True,
                high_flow="yes", two_speed_travel="yes", one_owner=True,
                copy_mode="dealer_clean", track_condition="75%",
                attachments_included="72 inch bucket, pallet forks"),
    {"net_hp": 92, "roc_lb": 3515, "tipping_load_lb": 7030,
     "operating_weight_lb": 11125, "hydraulic_flow_gpm": 23,
     "aux_flow_high_gpm": 36.6, "lift_path": "vertical",
     "width_over_tires_in": 74.4, "bucket_hinge_pin_height_in": 124.0},
    "compact_track_loader")

# 2. CTL — older, NOT low hour (should suppress low-hour claim)
out("CTL JD 333G (old, high hour)",
    DealerInput(year=2015, make="John Deere", model="333G", hours=4800,
                cab_type="enclosed", high_flow="yes",
                copy_mode="dealer_clean"),
    {"net_hp": 92, "roc_lb": 3700, "operating_weight_lb": 11400,
     "hydraulic_flow_gpm": 22, "aux_flow_high_gpm": 35,
     "lift_path": "vertical", "width_over_tires_in": 74},
    "compact_track_loader")

# 3. SSL — wheeled, no high flow
out("SSL Bobcat S650",
    DealerInput(year=2018, make="Bobcat", model="S650", hours=2200,
                cab_type="enclosed", ac=True, heater=True,
                high_flow="no", two_speed_travel="yes",
                tire_condition="80%", copy_mode="dealer_clean"),
    {"net_hp": 74, "roc_lb": 2690, "operating_weight_lb": 8327,
     "hydraulic_flow_gpm": 23, "lift_path": "vertical",
     "width_over_tires_in": 72},
    "skid_steer")

# 4. Mini ex — thumb, aux, low hour
out("Mini Ex Kubota KX033-4",
    DealerInput(year=2019, make="Kubota", model="KX033-4", hours=850,
                cab_type="enclosed", ac=True, heater=True,
                thumb_type="hydraulic", aux_hydraulics=True,
                blade_type="straight", zero_tail_swing=True,
                rubber_tracks=True, copy_mode="dealer_clean",
                attachments_included="12 in bucket, 24 in bucket, hydraulic thumb"),
    {"net_hp": 24.8, "operating_weight_lb": 7660,
     "max_dig_depth": "10 ft 4 in", "max_dig_depth_ft": 10.3,
     "tail_swing_type": "zero", "width_in": 60.6,
     "hydraulic_flow_gpm": 9.2},
    "mini_excavator")

# 5. Mini ex — no thumb claim should be stripped
out("Mini Ex Bobcat E35 (no thumb)",
    DealerInput(year=2020, make="Bobcat", model="E35", hours=1400,
                cab_type="enclosed", aux_hydraulics=True,
                copy_mode="dealer_clean"),
    {"net_hp": 24.8, "operating_weight_lb": 7689,
     "max_dig_depth_ft": 10.5, "width_in": 67},
    "mini_excavator")

# 6. Telehandler — capacity/height/reach
out("Telehandler JLG 742",
    DealerInput(year=2017, make="JLG", model="742", hours=2100,
                cab_type="enclosed", has_stabilizers=True, ac=True,
                attachments_included="48 in pallet forks",
                copy_mode="dealer_clean"),
    {"max_lift_capacity_lbs": 7000, "lift_height_ft": 42,
     "forward_reach_ft": 29, "operating_weight_lb": 24800,
     "net_hp": 117},
    "telehandler")

# 7. Wheel loader
out("Wheel Loader Cat 950M",
    DealerInput(year=2016, make="Caterpillar", model="950M", hours=8500,
                cab_type="enclosed", ride_control=True, ac=True,
                tire_condition="65%", copy_mode="dealer_clean"),
    {"net_hp": 250, "operating_weight_lb": 41888,
     "bucket_capacity_yd3": 4.5},
    "wheel_loader")

# 8. Excavator full-size
out("Excavator Cat 313FL",
    DealerInput(year=2018, make="Caterpillar", model="313FL", hours=4200,
                cab_type="enclosed", thumb_type="hydraulic",
                coupler_type="hydraulic", aux_hydraulics_type="combined",
                undercarriage_condition_pct="70%",
                undercarriage_percent_remaining=70,
                stick_arm_length_ft=8.2, copy_mode="dealer_clean"),
    {"net_hp": 95, "operating_weight_lb": 28925,
     "max_dig_depth_ft": 18.5, "max_reach_ft": 27.8},
    "excavator")

# 9. Marketplace short form
out("Mini Ex marketplace",
    DealerInput(year=2019, make="Kubota", model="KX033-4", hours=850,
                cab_type="enclosed", thumb_type="hydraulic",
                aux_hydraulics=True, blade_type="straight",
                copy_mode="marketplace_direct", asking_price=42500,
                attachments_included="hydraulic thumb, 12 in bucket"),
    {"net_hp": 24.8, "operating_weight_lb": 7660,
     "max_dig_depth_ft": 10.3, "width_in": 60.6},
    "mini_excavator", tone="marketplace_direct")

# 10. Tier C — known issue
out("CTL Tier C (mechanic special)",
    DealerInput(year=2014, make="Cat", model="259D", hours=5800,
                cab_type="open", condition_grade="Needs Work",
                condition_notes="Hydraulic leak at lift cylinder, runs but slow.",
                copy_mode="dealer_clean"),
    {"net_hp": 74, "roc_lb": 2150, "operating_weight_lb": 8810},
    "compact_track_loader")

# 11. Backhoe
out("Backhoe Case 580SN",
    DealerInput(year=2017, make="Case", model="580SN", hours=3400,
                cab_type="enclosed", ac=True,
                copy_mode="dealer_clean"),
    {"net_hp": 95, "operating_weight_lb": 14800},
    "backhoe_loader")

# 12. CTL — premium spec sheet
out("CTL premium spec sheet",
    DealerInput(year=2022, make="Kubota", model="SVL97-2", hours=420,
                cab_type="enclosed", heater=True, ac=True,
                high_flow="yes", two_speed_travel="yes",
                ride_control=True, self_leveling=True, reversing_fan=True,
                one_owner=True, track_condition="90%",
                copy_mode="premium_spec_sheet",
                attachments_included="80 in bucket, pallet forks, hydraulic thumb"),
    {"net_hp": 96.4, "roc_lb": 3000, "tipping_load_lb": 8580,
     "operating_weight_lb": 12125, "hydraulic_flow_gpm": 24,
     "aux_flow_high_gpm": 40, "lift_path": "vertical",
     "width_over_tires_in": 78.4},
    "compact_track_loader", tone="premium_spec_sheet")
