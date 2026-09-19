from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.database import init_db, get_db
from app.models import DepartmentModel, Corridor, Section, Line, Asset, Resource, RuleConfiguration
import json
from contextlib import asynccontextmanager

import logging
log = logging.getLogger(__name__)
