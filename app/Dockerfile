FROM node:20-bookworm-slim

WORKDIR /app

COPY app/package.json app/package-lock.json ./
RUN npm ci

COPY app/ ./

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

