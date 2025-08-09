from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="pronto-ai-bot",
    version="1.0.0",
    author="ProntoAI Team",
    author_email="hello@prontoai.xyz",
    description="A comprehensive Telegram bot for productivity management with AI assistance",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/w3sqr/ProntoAIBot",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "pronto-bot=bot:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
) 