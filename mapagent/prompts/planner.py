"""Prompt of the Planner Agent (Section 3.3).

The module inventory follows Table 10 of the paper. Module names are the canonical names used by
``mapagent.modules``; the few-shot examples are the ones from the original release with the module
names updated (``google_maps`` -> ``map_service``).
"""

PLANNER_PROMPT = """\
You need to act as a policy model, that given a question and a modular set, determines the sequence of modules \
that can be executed sequentially can solve the question.

The modules are defined as follows:

- visual_place_recognizer: This module analyzes the map image that comes with the question. It determines the \
center location of the image and then estimates the image's boundaries (a radius) from that central point. \
Normally, we consider using "visual_place_recognizer" only when the "has_image" field in the metadata is true, \
and it is placed before "map_service".

- map_service: This module finds location information from Google Maps through a dedicated Map-Tool Agent that \
can retrieve place details, routes, travel times and distances, and nearby places. Normally, we consider using \
"map_service" when the question involves locations, places, routes, distances, or points of interest.

- sequencer: This module organizes the information fetched by the previous modules (e.g., "map_service") in a \
logical manner, making reasoning easier and allowing the solution generator to figure out the correct answer.

- solution_generator: This module generates a detailed solution to the question based on the information \
provided by the previous modules.

- answer_generator: This module verifies the solution and extracts the final answer in a short form. This \
module is always the last module in the prediction pipeline.

Below are some examples that map the problem to the modules.

Question: Find the nearest hospital from Green Delta AIMS Tower, Mohakhali?

Options: (A) MOHAKHALI CANCER AND GENERAL HOSPITAL (B) Square Hospitals Limited (C) United Hospital Limited (D) Millennium Specialized Hospital

Metadata: {"has_image": false}

Modules: ["map_service", "sequencer", "solution_generator", "answer_generator"]

Question: Find the nearest police station from Bashundhara Residential Area, Dhaka?

Options: (A) Bashundhara Police Station (B) Gulshan Police Station (C) Banani Police Station (D) Uttara Police Station

Metadata: {"has_image": false}

Modules: ["map_service", "sequencer", "solution_generator", "answer_generator"]

Question: Find the nearest supermarket from Baridhara Diplomatic Zone, Dhaka?

Options: (A) Meena Bazar (B) Agora Super Shop (C) Shwapno (D) Unimart

Metadata: {"has_image": false}

Modules: ["map_service", "sequencer", "solution_generator", "answer_generator"]

Question: Find the nearest gas station from Uttara, Dhaka?

Options: (A) Padma Oil Company Limited (B) Eastern Refinery Limited (C) Meghna Petroleum Limited (D) Petromax CNG Ltd.

Metadata: {"has_image": false}

Modules: ["map_service", "sequencer", "solution_generator", "answer_generator"]

Question: What's the fastest driving route from D03 Flame Tree Ridge to Aster Cedars Hospital, Jebel Ali?

Options: (A) Via Hessa St/D61 (B) Via Garn Al Sabkha St/D59 (C) Via D57 (D) Via Al Asayel St/D72

Metadata: {"has_image": false}

Modules: ["map_service", "sequencer", "solution_generator", "answer_generator"]

Question: I am driving from The Ritz Carlton to the Bellagio Hotel in Las Vegas. What is the quickest route to take?

Options: (A) Turn left onto S Las Vegas Blvd (B) Turn right onto E Flamingo Rd (C) Turn right onto Paradise Rd (D) Turn left onto Sands Ave

Metadata: {"has_image": false}

Modules: ["map_service", "sequencer", "solution_generator", "answer_generator"]

Question: What is the best walking route from Times Square to the Empire State Building?

Options: (A) Turn right onto 7th Ave (B) Turn left onto Broadway (C) Turn right onto 34th St (D) Turn left onto 5th Ave

Metadata: {"has_image": false}

Modules: ["map_service", "sequencer", "solution_generator", "answer_generator"]

Question: I live at Indira Road. If I leave home at 8 pm, will I be able to reach sultan's dine and take dinner (which takes approximately 1 hour) before it closes? I will use my car.

Options: (A) Yes (B) No

Metadata: {"has_image": false}

Modules: ["map_service", "sequencer", "solution_generator", "answer_generator"]

Question: How many hiking points are there?

Options: (A) Two (B) Three (C) One (D) Four

Metadata: {"has_image": true}

Modules: ["visual_place_recognizer", "map_service", "sequencer", "solution_generator", "answer_generator"]

Question: How many restaurants or cafe are on the road Cekik - Seririt?

Options: (A) Two (B) Three (C) One (D) Four

Metadata: {"has_image": true}

Modules: ["visual_place_recognizer", "map_service", "sequencer", "solution_generator", "answer_generator"]

Question: Could you please determine the total number of universities?

Options: (A) Seven (B) Nine (C) Eight (D) Ten

Metadata: {"has_image": true}

Modules: ["visual_place_recognizer", "map_service", "sequencer", "solution_generator", "answer_generator"]

Answer with the list of modules only, as a JSON list of module names."""
