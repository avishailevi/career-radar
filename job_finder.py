jobs = [
    "Board Design Engineer",
    "Software Developer",
    "FPGA Engineer",
    "QA Tester",
    "Hardware Integration Engineer",
    "ASIC Verification Engineer"
]

keywords = [
    "Board",
    "FPGA",
    "Hardware",
    "ASIC",
    "Verification",
    "Integration"
]

print("Relevant jobs:")
print("--------------")

for job in jobs:
    for keyword in keywords:
        if keyword.lower() in job.lower():
            print(job)
            break