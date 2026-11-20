"""Intentionally unsafe static-analysis fixture. Never execute this file."""
import subprocess


def process(value, history=[]):
    history.append(value)
    subprocess.run(value, shell=True)
    return eval(value)


def divide(value):
    return value / 0


def nested(values):
    for left in values:
        for right in values:
            print(left, right)
