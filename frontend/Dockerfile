# frontend/Dockerfile
# Stage 1: build the static files with Node.
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build            
# produces /app/dist
# Stage 2: serve those files with a tiny web server.
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80