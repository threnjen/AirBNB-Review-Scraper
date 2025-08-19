docker network create weaviate-network

docker build -f Dockerfiles/Dockerfile.weaviate_rag -t weaviate .

docker build -f Dockerfiles/Dockerfile.t2v-transformers -t t2v-transformers .

docker run -d --name t2v-transformers --network weaviate-network --env-file weaviate.env t2v-transformers:latest

docker run -d -p 8080:8080 -p 8081:8081 -p 50051:50051 -v weaviate_data:/var/lib/weaviate --name weaviate --env-file weaviate.env --network weaviate-network weaviate:latest

<!-- docker build -f Dockerfiles/Dockerfile.rag_description_generation -t rag .

docker run --name rag --env-file weaviate.env --network weaviate-network rag:latest -->



Check docker containers running:

docker container ls