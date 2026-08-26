FROM node:20-slim AS development

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]

FROM development AS build

ARG VITE_API_URL=http://localhost:5000
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

FROM node:20-slim AS production

WORKDIR /app

RUN npm install -g serve@14

COPY --from=build /app/dist ./dist

ENV PORT=10000
EXPOSE 10000

CMD ["sh", "-c", "serve -s dist -l tcp://0.0.0.0:${PORT}"]
