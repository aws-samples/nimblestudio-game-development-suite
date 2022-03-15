import setuptools


with open("README.md") as fp:
    long_description = fp.read()


setuptools.setup(
    name="nimble_studio_game_development_suite",
    version="0.0.1",
    description="A CDK Python app to create infrastructure for Game Development on AWS for use with Amazon Nimble Studio",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="author",
    package_dir={"": "nimble_studio_game_development_suite"},
    packages=setuptools.find_packages(where="nimble_studio_game_development_suite"),
    install_requires=[
        "aws-cdk-lib>=2.5.0",
        "black>=21",
        "boto3>=1.20.0",
        "botocore>=1.23.0",
        "constructs>=10.0.0,<11.0.0",
    ],
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT No Attribution License (MIT-0)",
        "Programming Language :: JavaScript",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Utilities",
        "Typing :: Typed",
    ],
)
