"""
DevToolsPilot-CLI 安装配置
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

with open("devtools_pilot/__init__.py", "r", encoding="utf-8") as f:
    for line in f:
        if line.startswith("__version__"):
            version = line.split('"')[1]
            break
    else:
        version = "0.1.0"

setup(
    name="devtools-pilot-cli",
    version=version,
    description="轻量级终端Chrome DevTools智能控制引擎",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="DevToolsPilot Contributors",
    license="MIT",
    python_requires=">=3.8",
    packages=find_packages(exclude=["tests*"]),
    extras_require={
        "websocket": ["websockets>=10.0"],
    },
    entry_points={
        "console_scripts": [
            "devtools-pilot=devtools_pilot.__main__:entry_point",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP :: Browsers",
        "Topic :: Software Development :: Testing",
        "Environment :: Console",
    ],
)
