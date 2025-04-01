#### Set base image (host OS)
FROM python:3.11.7

#### By default, listen on port 8080
EXPOSE 8080/tcp

#### Set the working directory in the container
WORKDIR /

#### Copy the dependencies file to the working directory
COPY requirements.txt .

#### Install any dependencies
RUN pip install -r requirements.txt

#### Copy the content of the local src directory to the working directory
COPY . .

#### Specify the command to run on container start
CMD [ "python", "run.py" ]
