-- Runs once on first postgres startup
-- Creates the Airflow metadata DB and the two warehouse schemas

CREATE DATABASE airflow;

\c dataforge;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS warehouse;
