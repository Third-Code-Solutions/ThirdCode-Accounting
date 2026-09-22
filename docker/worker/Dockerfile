FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
COPY apps/worker/package.json apps/worker/package.json
COPY packages/contracts/package.json packages/contracts/package.json

RUN npm ci --no-audit --no-fund

COPY apps/worker apps/worker
COPY packages/contracts packages/contracts

RUN npm run build:worker

ENV NODE_ENV=production
ENV WORKER_ENV=production
EXPOSE 3001

CMD ["node", "apps/worker/dist/index.js"]
