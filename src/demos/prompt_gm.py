# prompt for generating input for google maps
prompt_1 = """
Read the following question and metadata, then extract information about query, location, region and type and current_location and give as 
json format.

Question: Find the nearest hospital from Green Delta AIMS Tower, Mohakhali?

Options: (A) MOHAKHALI CANCER AND GENERAL HOSPITAL (B) Square Hospitals Limited (c) United Hospital Limited (d) Millennium Specialized Hospital

Metadata: {"skill":"Fetch Information from map and mention the POI"}

Information: { 
        query="Find all the Hospital",
        location="Mohakhali",
        region="Dhaka",
        type="Hospital",
        current_location="Green Delta AIMS Tower, Mohakhali"
}


Question: Find the nearest police station from Bashundhara Residential Area, Dhaka?

Options: (A) Bashundhara Police Station (B) Gulshan Police Station (C) Banani Police Station (D) Uttara Police Station

Metadata: {"skill":"Fetch Information from map and mention the POI"}

Information: { 
        query="Find all the Police Stations", 
        location="Bashundhara Residential Area", 
        region="Dhaka", 
        type="Police Station", 
        current_location="Bashundhara Residential Area, Dhaka" 
}


Question: Find the nearest supermarket from Baridhara Diplomatic Zone, Dhaka?

Options: (A) Meena Bazar (B) Agora Super Shop (C) Shwapno (D) Unimart

Metadata: {"skill":"Fetch Information from map and mention the POI"}

Information: { 
        query="Find all the Supermarkets", 
        location="Baridhara Diplomatic Zone", 
        region="Dhaka", 
        type="Supermarket", 
        current_location="Baridhara Diplomatic Zone, Dhaka" 
}


Question: Find the nearest gas station from Uttara, Dhaka?

Options: (A) Padma Oil Company Limited (B) Eastern Refinery Limited (C) Meghna Petroleum Limited (D) Petromax CNG Ltd.

Metadata: {"skill":"Fetch Information from map and mention the POI"}

Information: { 
        query="Find all the Gas Stations", 
        location="Uttara", 
        region="Dhaka", 
        type="Gas Station", 
        current_location="Uttara, Dhaka" 
}



Read the following question and metadata, then extract information about query, location, region and type and current_location and give as 
json format. Put only the five fields: query, location, region, type and current_location.
"""

# prompt for question and using the information find the
prompt_2 = """
Read the following question and metadata, and generate the query for browser search as the context information that could be helpful for answering the question.

Question: Which property do these two objects have in common?

Options: (A) hard (B) bendable

Metadata: {'pid': 329, 'has_image': True, 'grade': 2, 'subject': 'natural science', 'topic': 'physics', 'category': 'Materials', 'skill': 'Compare properties of objects'}

Detected text in the image: [([[41, 183], [131, 183], [131, 199], [41, 199]], 'rubber gloves'), ([[245, 183], [313, 183], [313, 197], [245, 197]], 'rain boots')]

Search Query: Common material properties of jump tope and rubber gloves





Question: Which better describes the Shenandoah National Park ecosystem? 

Context: Figure: Shenandoah National Park.\nShenandoah National Park is a temperate deciduous forest ecosystem in northern Virginia.

Options: (A) It has warm, wet summers. It also has only a few types of trees. (B) It has cold, wet winters. It also has soil that is poor in nutrients.

Metadata: {'pid': 246, 'has_image': True, 'grade': 3, 'subject': 'natural science', 'topic': 'biology', 'category': 'Ecosystems', 'skill': 'Describe ecosystems'}

Search Query: Temperature and climate of Shenandoah National Park ecosystem





Question: Does this passage describe the weather or the climate? 

Context: Figure: Marseille.\nMarseille is a town on the southern coast of France. Cold winds from the north, called mistral winds, are common in Marseille each year during late winter and early spring.\nHint: Weather is what the atmosphere is like at a certain place and time. Climate is the pattern of weather in a certain place. 

Options: (A) weather (B) climate

Metadata: {'pid': 321, 'has_image': True, 'grade': 5, 'subject': 'natural science', 'topic': 'earth-science', 'category': 'Weather and climate', 'skill': 'Weather and climate around the world'}

Query: Weather or climate of Marseille, France



Question: Is the following statement about our solar system true or false?\nJupiter's volume is more than ten times as large as Saturn's volume. 

Context: Use the data to answer the question below. 

Options: (A) true (B) false

Metadata: {'pid': 649, 'has_image': True, 'grade': 8, 'subject': 'natural science', 'topic': 'earth-science', 'category': 'Astronomy', 'skill': 'Analyze data to compare properties of planets'}

Query: Volume comparison between Jupiter and Saturn



Read the following question and metadata, and generate the query for browser search as the context information that could be helpful for answering the question.
"""

# prompt for generating input for google maps
prompt_3 = """
Read the following question and metadata, and generate the query for browser search as the context information that could be helpful for answering the question.

Question: Which property do these two objects have in common?

Options: (A) hard (B) bendable

Metadata: {'pid': 329, 'has_image': True, 'grade': 2, 'subject': 'natural science', 'topic': 'physics', 'category': 'Materials', 'skill': 'Compare properties of objects'}

Detected text in the image: [([[41, 183], [131, 183], [131, 199], [41, 199]], 'rubber gloves'), ([[245, 183], [313, 183], [313, 197], [245, 197]], 'rain boots')]

Search Query: Common material properties of jump tope and rubber gloves





Question: Which better describes the Shenandoah National Park ecosystem? 

Context: Figure: Shenandoah National Park.\nShenandoah National Park is a temperate deciduous forest ecosystem in northern Virginia.

Options: (A) It has warm, wet summers. It also has only a few types of trees. (B) It has cold, wet winters. It also has soil that is poor in nutrients.

Metadata: {'pid': 246, 'has_image': True, 'grade': 3, 'subject': 'natural science', 'topic': 'biology', 'category': 'Ecosystems', 'skill': 'Describe ecosystems'}

Search Query: Temperature and climate of Shenandoah National Park ecosystem





Question: Does this passage describe the weather or the climate? 

Context: Figure: Marseille.\nMarseille is a town on the southern coast of France. Cold winds from the north, called mistral winds, are common in Marseille each year during late winter and early spring.\nHint: Weather is what the atmosphere is like at a certain place and time. Climate is the pattern of weather in a certain place. 

Options: (A) weather (B) climate

Metadata: {'pid': 321, 'has_image': True, 'grade': 5, 'subject': 'natural science', 'topic': 'earth-science', 'category': 'Weather and climate', 'skill': 'Weather and climate around the world'}

Query: Weather or climate of Marseille, France



Question: Is the following statement about our solar system true or false?\nJupiter's volume is more than ten times as large as Saturn's volume. 

Context: Use the data to answer the question below. 

Options: (A) true (B) false

Metadata: {'pid': 649, 'has_image': True, 'grade': 8, 'subject': 'natural science', 'topic': 'earth-science', 'category': 'Astronomy', 'skill': 'Analyze data to compare properties of planets'}

Query: Volume comparison between Jupiter and Saturn



Read the following question and metadata, and generate the query for browser search as the context information that could be helpful for answering the question.
"""

# prompt for generating input for google maps
prompt_4 = """
Read the following question and metadata, and generate the query for browser search as the context information that could be helpful for answering the question.

Question: Which property do these two objects have in common?

Options: (A) hard (B) bendable

Metadata: {'pid': 329, 'has_image': True, 'grade': 2, 'subject': 'natural science', 'topic': 'physics', 'category': 'Materials', 'skill': 'Compare properties of objects'}

Detected text in the image: [([[41, 183], [131, 183], [131, 199], [41, 199]], 'rubber gloves'), ([[245, 183], [313, 183], [313, 197], [245, 197]], 'rain boots')]

Search Query: Common material properties of jump tope and rubber gloves





Question: Which better describes the Shenandoah National Park ecosystem? 

Context: Figure: Shenandoah National Park.\nShenandoah National Park is a temperate deciduous forest ecosystem in northern Virginia.

Options: (A) It has warm, wet summers. It also has only a few types of trees. (B) It has cold, wet winters. It also has soil that is poor in nutrients.

Metadata: {'pid': 246, 'has_image': True, 'grade': 3, 'subject': 'natural science', 'topic': 'biology', 'category': 'Ecosystems', 'skill': 'Describe ecosystems'}

Search Query: Temperature and climate of Shenandoah National Park ecosystem





Question: Does this passage describe the weather or the climate? 

Context: Figure: Marseille.\nMarseille is a town on the southern coast of France. Cold winds from the north, called mistral winds, are common in Marseille each year during late winter and early spring.\nHint: Weather is what the atmosphere is like at a certain place and time. Climate is the pattern of weather in a certain place. 

Options: (A) weather (B) climate

Metadata: {'pid': 321, 'has_image': True, 'grade': 5, 'subject': 'natural science', 'topic': 'earth-science', 'category': 'Weather and climate', 'skill': 'Weather and climate around the world'}

Query: Weather or climate of Marseille, France



Question: Is the following statement about our solar system true or false?\nJupiter's volume is more than ten times as large as Saturn's volume. 

Context: Use the data to answer the question below. 

Options: (A) true (B) false

Metadata: {'pid': 649, 'has_image': True, 'grade': 8, 'subject': 'natural science', 'topic': 'earth-science', 'category': 'Astronomy', 'skill': 'Analyze data to compare properties of planets'}

Query: Volume comparison between Jupiter and Saturn



Read the following question and metadata, and generate the query for browser search as the context information that could be helpful for answering the question.
"""

# prompt for generating input for google maps
prompt_5 = """
Read the following question and metadata, and generate the query for browser search as the context information that could be helpful for answering the question.

Question: Which property do these two objects have in common?

Options: (A) hard (B) bendable

Metadata: {'pid': 329, 'has_image': True, 'grade': 2, 'subject': 'natural science', 'topic': 'physics', 'category': 'Materials', 'skill': 'Compare properties of objects'}

Detected text in the image: [([[41, 183], [131, 183], [131, 199], [41, 199]], 'rubber gloves'), ([[245, 183], [313, 183], [313, 197], [245, 197]], 'rain boots')]

Search Query: Common material properties of jump tope and rubber gloves





Question: Which better describes the Shenandoah National Park ecosystem? 

Context: Figure: Shenandoah National Park.\nShenandoah National Park is a temperate deciduous forest ecosystem in northern Virginia.

Options: (A) It has warm, wet summers. It also has only a few types of trees. (B) It has cold, wet winters. It also has soil that is poor in nutrients.

Metadata: {'pid': 246, 'has_image': True, 'grade': 3, 'subject': 'natural science', 'topic': 'biology', 'category': 'Ecosystems', 'skill': 'Describe ecosystems'}

Search Query: Temperature and climate of Shenandoah National Park ecosystem





Question: Does this passage describe the weather or the climate? 

Context: Figure: Marseille.\nMarseille is a town on the southern coast of France. Cold winds from the north, called mistral winds, are common in Marseille each year during late winter and early spring.\nHint: Weather is what the atmosphere is like at a certain place and time. Climate is the pattern of weather in a certain place. 

Options: (A) weather (B) climate

Metadata: {'pid': 321, 'has_image': True, 'grade': 5, 'subject': 'natural science', 'topic': 'earth-science', 'category': 'Weather and climate', 'skill': 'Weather and climate around the world'}

Query: Weather or climate of Marseille, France



Question: Is the following statement about our solar system true or false?\nJupiter's volume is more than ten times as large as Saturn's volume. 

Context: Use the data to answer the question below. 

Options: (A) true (B) false

Metadata: {'pid': 649, 'has_image': True, 'grade': 8, 'subject': 'natural science', 'topic': 'earth-science', 'category': 'Astronomy', 'skill': 'Analyze data to compare properties of planets'}

Query: Volume comparison between Jupiter and Saturn



Read the following question and metadata, and generate the query for browser search as the context information that could be helpful for answering the question.
"""