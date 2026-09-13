FROM node:22-slim AS base

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .

ENV NODE_ENV=production
RUN npm run build

EXPOSE 3000
ENV PORT=3000

CMD ["npm", "start"]
