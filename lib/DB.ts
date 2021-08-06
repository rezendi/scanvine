const options = {};
const pgp = require('pg-promise')(options);
const connectionString = process.env.DATABASE_URL;

const fs = require('fs');
const certPath = '/app/config/do-pg-client.crt';
const certPathExists = fs.existsSync(certPath);
const connectionOptions = certPathExists ? {connectionString, ssl:{ cert: fs.readFileSync(certPath) }} : connectionString;
const db = pgp(connectionOptions);

async function doCreate() {
    let exists_query = "SELECT * FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'lines'";
    try {
        let exists_results = await db.any(exists_query);
        // console.log("exists", exists_results);
        if (exists_results.length==0) {
          console.log("Creating DB");
          let users_query = "CREATE TABLE IF NOT EXISTS Users (id serial PRIMARY KEY, status INTEGER DEFAULT 0";
          users_query += ", email VARCHAR(255), name VARCHAR(255), username VARCHAR(255), twitter VARCHAR(255)";
          users_query += ", github VARCHAR(255), metadata JSONB, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
          await db.none(users_query);
          let uploads_query = "CREATE TABLE IF NOT EXISTS Uploads (id serial PRIMARY KEY, user_id INTEGER, status INTEGER DEFAULT 0";
          uploads_query += ", url VARCHAR(255), metadata JSONB, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP";
          uploads_query += ", FOREIGN KEY (user_id) REFERENCES Users (id))";
          await db.none(uploads_query);
          let indexes_query = "CREATE INDEX userid_index ON Uploads (user_id); ";
          await db.none(indexes_query);
        }
    } catch(error) {
        console.log("create DB error", error);
    }
}

async function doUpdate() {
    let update_query = "";
    if (update_query) {
      try {
        console.log("updating DB");
        let update_results = await db.any(update_query);
        console.log("results", update_results);
      } catch(error) {
        console.log("update DB error", error);
      }
    }
  }
  
  doCreate();
  doUpdate();
  
  /* Lines */
  
  async function getUploads(userid:number = 0) {
      let query = `SELECT * FROM Uploads ORDER BY created_at DESC`;
      if (userid > 0) {
        query = "SELECT * FROM Uploads WHERE user_id = $1 ORDER BY created_at DESC ";
        return await db.any(query, [userid]);
      }
      return await db.any(query);
  }
  
  async function saveUpload(userid:number, url:string) {
    try {
        let query = "INSERT INTO Uploads (user_id, url) VALUES ($1, $2) RETURNING *";
        return await db.one(query, [userid, url]);
    } catch(error) {
        console.log("DB error saving upload", error);
        throw(error);
    }
  }
  
  export default {
    getUploads,
    saveUpload,
}
  