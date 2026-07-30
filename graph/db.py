"""One place the database lives, so moving it to Aura is a variable, not a sweep.

Defaults are the local container — nothing changes for local dev if the env is unset.
"""
import os, pathlib
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(pathlib.Path(__file__).resolve().parent.parent / ".env")

URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
USER = os.environ.get("NEO4J_USER", "neo4j")
PASSWORD = os.environ.get("NEO4J_PASSWORD", "hackvideo2026")


def driver():
    return GraphDatabase.driver(URI, auth=(USER, PASSWORD))
