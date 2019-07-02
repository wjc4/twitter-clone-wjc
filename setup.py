from setuptools import setup, find_packages

setup(
    name="twitter-clone",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    entry_points={
        "console_scripts": [
            "twitter-clone-hello = twitter_clone.cli:hello",
            "twitter-clone = twitter_clone.run:main",
        ]
    },
    install_requires=["Flask", "boto3", "redis"],
)
