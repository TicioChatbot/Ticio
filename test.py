from dotenv import load_dotenv
import os
from inference import inference

load_dotenv()

x = input()
print(inference(x))
