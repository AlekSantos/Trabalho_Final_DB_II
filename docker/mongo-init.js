// mongo-init.js — inicia o replica set rs0 apenas se ele ainda não existir.
// Executado automaticamente pelo serviço "mongo-init" do docker-compose.yml.
// Também pode ser rodado manualmente:
//   docker exec -it mongo1 mongosh --host mongo1:27017 /mongo-init.js

try {
  const status = rs.status();
  print("Replica set já estava iniciado (estado atual): " + status.myState);
} catch (erro) {
  if (erro.codeName === "NotYetInitialized" || erro.code === 94) {
    print("Replica set ainda não iniciado. Iniciando rs0...");
    const resultado = rs.initiate({
      _id: "rs0",
      members: [
        { _id: 0, host: "mongo1:27017" },
        { _id: 1, host: "mongo2:27017" },
        { _id: 2, host: "mongo3:27017" },
      ],
    });
    printjson(resultado);
  } else {
    print("Erro inesperado ao verificar o status do replica set:");
    printjson(erro);
    quit(1);
  }
}
