# Use the official Node.js image
FROM node:20-alpine

# Set the working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the source code
COPY . .

# Expose the Vite port
EXPOSE 5173

# Command to run the Vite development server
CMD ["npm", "run", "dev"]