# Entry point cho Vercel Python (serverless): Vercel tu dong nhan dien
# cac file trong thu muc api/ va chay Flask app duoc export tai day.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app  # noqa: F401  (Vercel dung bien `app` lam WSGI handler)
