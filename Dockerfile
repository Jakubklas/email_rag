# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory
WORKDIR /WORKIR

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Set the default command (optional)
CMD ["python run app.py"]