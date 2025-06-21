

# cot
prompt_cot = """

Given the question (and the context), select the answer from the options ["A", "B", "C", "D", "E"]. You should give consice and step-by-step solutions. Finally, conclude the answer in the format of "the answer is [ANSWER]", where [ANSWER] is one from the options ["A", "B", "C", "D", "E"]. For example, "the answer is A", "the answer is B", "the answer is C", "the answer is D", or "the answer is E". If the answer is not in the options, select the most possible option.

Question: Which property do these two objects have in common?

Context: Select the better answer. Image: A pair of scissors next to a pair of scissors.

Options: (A) hard (B) bendable

Solution: An object has different properties. A property of an object can tell you how it looks, feels, tastes, or smells.\nDifferent objects can have the same properties. You can use these properties to put objects into groups. Look at each object.\nFor each object, decide if it has that property.\nA bendable object can be bent without breaking. Both objects are bendable.\nA hard object keeps its shape when you squeeze it. The rubber gloves are not hard.\nThe property that both objects have in common is bendable.\n\nTherefore, the answer is B.

Question: Select the one substance that is not a mineral.

Context: Select the better answer.

Options: (A) turtle shell is not a pure substance. It is made by a living thing (B) Celestine is a pure substance. It is a solid. (C) Hematite is not made by living things. It is a solid.

Solution: Compare the properties of each substance to the properties of minerals. Select the substance whose properties do not match those of minerals.\nA turtle shell is made by a living thing. But minerals are not made by living things.\nA turtle shell is not a pure substance. But all minerals are pure substances.\nSo, a turtle shell is not a mineral.\nCelestine is a mineral.\nHematite is a mineral.\nTherefore, the answer is A.
"""

# chameleon
prompt_chameleon = """
Given the question (and the context), select the answer from the options ["A", "B", "C", "D"]. You should give consice and step-by-step solutions. Finally, conclude the answer in the format of "the answer is [ANSWER]", where [ANSWER] is one from the options ["A", "B", "C", "D"]. For example, "the answer is A", "the answer is B", "the answer is C", or "the answer is D". If the answer is not in the options, select the most possible option.

#Example 1
Question: What is the address of Multiplan Center?

Options: (A) 69, 71 New Elephant Rd, Dhaka 1205, Bangladesh  (B) 38/1/C BC DAS Street Lalbagh  (C)Polashi,BUET  (D) Central Road, USA

Metadata: {"skill":"Fetch context from corresponding google map api and based on the context answer the question"}

google maps response: Multiplan Center
Name: Multiplan Center
Address: 69, 71 New Elephant Rd, Dhaka 1205, Bangladesh
Rating: 4.4
Types: point_of_interest, establishment
Is Open Now: False
Weekday Opening Hours:
- Monday: 10:00AM–8:00PM
- Tuesday: Closed
- Wednesday: 10:00AM–8:00PM
- Thursday: 10:00AM–8:00PM
- Friday: 10:00AM–8:00PM
- Saturday: 10:00AM–8:00PM
- Sunday: 10:00AM–8:00PM

Solution: If you look at the context and search, then after reaching The address of Multiplan Center is 69, 71 New Elephant Rd, Dhaka 1205, Bangladesh. Therefore, the answer is B.

#Example 2
Question: I am going from Indira Road to Chillox Dhanmondi by car via mirpur road.After reaching manik mia avenue where should I go next?

Options: (A) 'Turn right onto Road no 16'  (B)'Turn left onto Mirpur road'  (C)'Turn left onto indira road'  (D)'Turn right onto new elephant road'

Metadata: {"skill":"Fetch context from corresponding google map api and based on the context answer the question"}

google maps response:
There are total 1 routes from Indira Road to Chillox Dhanmondi. The route information is provided below:
Route 1: VIA Satmasjid Road will cover 3.9 km in 11 mins
Details steps are provided below: 
Head west on Indira Rd toward W Raza Bazar Rd will cover 40 m in 1 min 
Turn right at the 1st cross street onto W Raza Bazar Rd will cover 14 m in 1 min 
Turn left onto Indira Rd will cover 82 m in 1 min 
At the roundabout, take the 2nd exit will cover 73 m in 1 min 
Continue onto Manik Mia Ave will cover 0.8 km in 2 mins 
Turn left onto Mirpur Rd will cover 0.3 km in 1 min 
Turn right onto Road No 16 will cover 1.0 km in 3 mins 
Turn left onto Satmasjid Road will cover 1.5 km in 5 mins 
Make a U-turn at Road No. 3ADestination will be on the left will cover 66 m in 1 min 

Solution: If you look at the context and search, then after reaching Manik Mia Avenue, you should turn left onto Mirpur Rd because it is the next step after reaching Manik Mia Avenue. Therefore, the answer is B.

#Example 3
Question: Find the nearest hospital from Green Delta AIMS Tower, Mohakhali?

Options: (A) MOHAKHALI CANCER AND GENERAL HOSPITAL (B) National Institute of Diseases of the Chest and Hospital (c) United Hospital Limited (d) Millennium Specialized Hospital

Metadata: {"skill":"Fetch Information from map and mention the POI"}

google maps response: There are some hospital distance from the current location Green Delta AIMS Tower, Mohakhali in below:
Impulse Hospital (rating:3.8, number of people gives review: 528, distance from Green Delta AIMS Tower, Mohakhali: 1.65810016123089 kilometers)
AMZ Hospital Ltd. (rating:4, number of people gives review: 268, distance from Green Delta AIMS Tower, Mohakhali: 1.905227966928624 kilometers)
Square Hospital (rating:4.1, number of people gives review: 2639, distance from Green Delta AIMS Tower, Mohakhali: 4.068450279284913 kilometers)
United Hospital Limited (rating:3.9, number of people gives review: 1835, distance from Green Delta AIMS Tower, Mohakhali: 2.810382237654217 kilometers)
BIRDEM General Hospital (rating:4.2, number of people gives review: 1472, distance from Green Delta AIMS Tower, Mohakhali: 4.762908619455911 kilometers)
Central Hospital Limited (rating:3.9, number of people gives review: 705, distance from Green Delta AIMS Tower, Mohakhali: 4.774653552567642 kilometers)
Bangladesh Specialized Hospital (rating:3.4, number of people gives review: 1236, distance from Green Delta AIMS Tower, Mohakhali: 4.597114747999699 kilometers)
City Hospital & Diagnostic Center (rating:3.8, number of people gives review: 374, distance from Green Delta AIMS Tower, Mohakhali: 5.213372421229639 kilometers)
National Institute of Diseases of the Chest and Hospital (rating:4.2, number of people gives review: 584, distance from Green Delta AIMS Tower, Mohakhali: 0.544022687017918 kilometers)
Badda General Hospital Pvt. Ltd. (rating:3.7, number of people gives review: 118, distance from Green Delta AIMS Tower, Mohakhali: 1.8612444354946194 kilometers)
Hitech Multicare Hospital ltd (rating:3.7, number of people gives review: 377, distance from Green Delta AIMS Tower, Mohakhali: 2.172025093284416 kilometers)
Al Helal Specialized Hospital, Dhaka (rating:3.5, number of people gives review: 261, distance from Green Delta AIMS Tower, Mohakhali: 4.506883674695464 kilometers)
Better Life Hospital (rating:3.4, number of people gives review: 259, distance from Green Delta AIMS Tower, Mohakhali: 2.6071595159429655 kilometers)
AL-MANAR HOSPITAL LTD. (rating:4, number of people gives review: 337, distance from Green Delta AIMS Tower, Mohakhali: 5.298530088879729 kilometers)
Samorita Hospital Ltd. (rating:4, number of people gives review: 507, distance from Green Delta AIMS Tower, Mohakhali: 3.8567577415160033 kilometers)
Metropolitan Medical Centre Ltd. (rating:3.8, number of people gives review: 169, distance from Green Delta AIMS Tower, Mohakhali: 1.1906969840899404 kilometers)
Monowara Hospital (Pvt.) Ltd. (rating:3.8, number of people gives review: 368, distance from Green Delta AIMS Tower, Mohakhali: 4.139612397567985 kilometers)
Sheikh Russel National Gastroliver Institute & Hospital (rating:4.2, number of people gives review: 513, distance from Green Delta AIMS Tower, Mohakhali: 0.6135741921102021 kilometers)
Shaheed Suhrawardy Medical College and Hospital (rating:4.2, number of people gives review: 1617, distance from Green Delta AIMS Tower, Mohakhali: 3.9091223069781225 kilometers)
DNCC Dedicated Covid-19 Hospital, Mohakhali, Dhaka-1212 (rating:4.2, number of people gives review: 419, distance from Green Delta AIMS Tower, Mohakhali: 0.9847498438704613 kilometers)

Solution: Compared to all the hospitals near your current location at Green Delta AIMS Tower, Mohakhali,
we found National Institute of Diseases of the Chest and Hospital to be the closest. We can confirm that National Institute of Diseases of the Chest and Hospital is indeed the nearest option.\n
Therefore, the answer is B.

#Example 4
Question: Find the nearest Restaurant from West End School, Lalbagh, Dhaka?

Options: (A) Cafe Jannat Hotel & Restaurant (B) PIZZA Garage (C) Water Garden Restaurant & Convention Hall (D) Bhooter Bari Restaurant

Metadata: {"skill":"Fetch context from corresponding google map api and based on the context answer the question"}

google maps response: There are some restaurant distance from the current location West End School, Lalbagh, Dhaka in below:
New Dhanmondi Restora (rating:3.9, number of people gives review: 116, distance from West End School, Lalbagh, Dhaka: 3.0413553623267346 kilometers)
Zaytun Restaurant (rating:3.9, number of people gives review: 1285, distance from West End School, Lalbagh, Dhaka: 6.3839113657480695 kilometers)
Khaje Dewan Restaurant (rating:3.8, number of people gives review: 37, distance from West End School, Lalbagh, Dhaka: 0.6752691881527221 kilometers)
The Dinning Hall (rating:4.1, number of people gives review: 351, distance from West End School, Lalbagh, Dhaka: 0.41313362772319384 kilometers)
Bhooter Bari Restaurant (rating:4, number of people gives review: 2125, distance from West End School, Lalbagh, Dhaka: 0.3571511328124262 kilometers)
Pafin Chinese Restaurant Lalbagh (rating:4, number of people gives review: 428, distance from West End School, Lalbagh, Dhaka: 0.5283389241397418 kilometers)
Royal Restaurant (rating:4, number of people gives review: 5225, distance from West End School, Lalbagh, Dhaka: 0.5750237305248831 kilometers)
Mughal Darbar Restaurant (rating:4, number of people gives review: 105, distance from West End School, Lalbagh, Dhaka: 0.28708285974538417 kilometers)
Cafe Jannat Hotel & Restaurant (ক্যাফে জান্নাত হোটেল এন্ড রেস্টুরেন্ট) (rating:4.1, number of people gives review: 187, distance from West End School, Lalbagh, Dhaka: 0.27615569809162305 kilometers)
স্বাদের খাবার রেষ্টুরেন্ট (rating:4.8, number of people gives review: 6, distance from West End School, Lalbagh, Dhaka: 2.7487849956619743 kilometers)
Farook Hotel & Restaurant (rating:3.6, number of people gives review: 39, distance from West End School, Lalbagh, Dhaka: 1.8919381159012683 kilometers)
Park View Restaurant & Cafe (rating:4.4, number of people gives review: 7, distance from West End School, Lalbagh, Dhaka: 0.8970974676376949 kilometers)
Water Garden Restaurant & Convention Hall (rating:3.9, number of people gives review: 141, distance from West End School, Lalbagh, Dhaka: 0.2446427209784578 kilometers)
Shadhin Restaurant (rating:3.5, number of people gives review: 216, distance from West End School, Lalbagh, Dhaka: 2.246019915190759 kilometers)
SIDE KITCHEN (rating:4.6, number of people gives review: 9, distance from West End School, Lalbagh, Dhaka: 4.338917960755217 kilometers)
Food Corner Restaurant (rating:4.8, number of people gives review: 4, distance from West End School, Lalbagh, Dhaka: 3.37627183120816 kilometers)
Ghorowa Hotel & Restaurant (rating:3.5, number of people gives review: 64, distance from West End School, Lalbagh, Dhaka: 1.9709185385820103 kilometers)
B cafe or Take a bite restaurent & party center (rating:3.5, number of people gives review: 134, distance from West End School, Lalbagh, Dhaka: 0.437305811091622 kilometers)
Thirty3 Restaurant Dhanmondi (rating:4.1, number of people gives review: 53, distance from West End School, Lalbagh, Dhaka: 3.264829777424044 kilometers)

Solution: Compared to all the restaurant near your current location at West End School, Lalbagh, Dhaka,
we found Water Garden Restaurant & Convention Hall to be the closest. We can confirm that Water Garden Restaurant & Convention Hall is indeed the nearest option.\n
Therefore, the answer is C.

#Example 5
Question: I live on Indira Road. I need to go to LABAID Specialized hospital. I will stay there for half an hour. But I also need to go to Sultan's Dine Jigatola. I will have my dinner there, which will take approximately an hour. If I leave home at 8:30 pm, where should I go first? LABAID or Sultan's Dine. I will go by car.

Options: (A) "Sultan's Dine" (B)'LABAID Specialized Hospital'

Metadata: {"skill":"Fetch context from corresponding google map api and based on the context answer the question"}

All Location Info: 
Indira Road 
Name: Indira Gandhi Road
Address: Indira Gandhi Rd, Jamnagar, Gujarat, India
Rating: N/A
Types: route
Is Open Now: N/A
Weekday Opening Hours:
- Unknown
LABAID Specialized hospital 
Name: LABAID Specialized Hospital
Address: House- -1 and, 6, Road No. 4, Dhaka 1205, Bangladesh
Rating: 3.7
Types: hospital, health, point_of_interest, establishment
Is Open Now: True
Weekday Opening Hours:
- Monday: Open 24 hours
- Tuesday: Open 24 hours
- Wednesday: Open 24 hours
- Thursday: Open 24 hours
- Friday: Open 24 hours
- Saturday: Open 24 hours
- Sunday: Open 24 hours
Sultan's Dine Jigatola 
Name: Sultan's Dine, Dhanmondi Branch
Address: Green Akshay Plaza, 1st Floor, 146/G (Old), 59, New সাতমসজিদ সড়ক, ঢাকা 1209, Bangladesh
Rating: 4.2
Types: restaurant, food, point_of_interest, establishment
Is Open Now: True
Weekday Opening Hours:
- Monday: 12:00PM–4:00AM
- Tuesday: 12:00PM–4:00AM
- Wednesday: 12:00PM–4:00AM
- Thursday: 12:00PM–4:00AM
- Friday: 12:00PM–4:00AM
- Saturday: 12:00PM–4:00AM
- Sunday: 12:00PM–4:00AM
The travel time(distance) from Indira Road to LABAID Specialized hospital is 9 mins (3.2 km)
The travel time(distance) from Indira Road to Sultan's Dine Jigatola is 12 mins (4.2 km)
The travel time(distance) from LABAID Specialized hospital to Indira Road is 11 mins (2.6 km)
The travel time(distance) from LABAID Specialized hospital to Sultan's Dine Jigatola is 5 mins (1.1 km)
The travel time(distance) from Sultan's Dine Jigatola to Indira Road is 22 mins (5.6 km)
The travel time(distance) from Sultan's Dine Jigatola to LABAID Specialized hospital is 15 mins (3.3 km)

Solution: To determine where to go first, we need to consider the total time it will take to visit both places.
If you leave home at 8:30 pm and go to LABAID Specialized Hospital first, it will take you 9 minutes to get there. Then, you will stay there for half an hour. After that, you have to go to Sultan's Dine, which takes about 5 minutes, and you will spend 1 hour there. When you return back home, it will take 22 minutes. This means you will have spent 126 minutes in total (9 + 30 + 5 + 60 + 22).
On the other hand, if you leave home at 8:30 pm and go to Sultan's Dine Jigatola first, it will take you 12 minutes to get there. Then, you will have dinner for approximately an hour. After that, you have to go to LABAID Specialized Hospital, which will take you 15 minutes, and you will stay there for 30 minutes. From LABAID, you need 11 minutes to get back home. This means you will have spent a total of 128 minutes (12 + 60 + 15 + 30 + 11).
Based on the total time it will take to visit both places, it is better to go to LABAID Specialized Hospital first.
Therefore, the answer is B.

Now Answer the question following.
#Question

"""
