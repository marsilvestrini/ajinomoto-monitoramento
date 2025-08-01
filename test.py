from dotenv import load_dotenv
import os
from datetime import datetime
load_dotenv()


if os.getenv('SAVE_RESULTS'):
    print(datetime.now())