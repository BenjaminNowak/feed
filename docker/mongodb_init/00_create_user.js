// Read credentials from Docker secrets
const fs = require('fs');

let username, password;

try {
    // Read from Docker secrets files
    username = fs.readFileSync('/run/secrets/mongo_username', 'utf8').trim();
    password = fs.readFileSync('/run/secrets/mongo_password', 'utf8').trim();
} catch (error) {
    print("Error reading secrets: " + error.message);
    print("Falling back to environment variables");
    
    // Fallback to environment variables if secrets are not available
    username = process.env.MONGO_INITDB_ROOT_USERNAME || 'feeduser';
    password = process.env.MONGO_INITDB_ROOT_PASSWORD || 'changeme';
}

print("Initializing MongoDB with user: " + username);

// Switch to admin database to create user
db = db.getSiblingDB('admin');

// Create the root user if it doesn't exist
if (db.getUser(username) == null) {
    db.createUser({
        user: username,
        pwd: password,
        roles: [
            { role: "userAdminAnyDatabase", db: "admin" },
            { role: "readWriteAnyDatabase", db: "admin" },
            { role: "dbAdminAnyDatabase", db: "admin" }
        ]
    });
    print("Root user '" + username + "' created successfully");
}

// Switch to feeddb database
db = db.getSiblingDB('feeddb');

// Create application user for feeddb if it doesn't exist
if (db.getUser(username) == null) {
    db.createUser({
        user: username,
        pwd: password,
        roles: [
            { role: "readWrite", db: "feeddb" },
            { role: "dbAdmin", db: "feeddb" }
        ]
    });
    print("Database user '" + username + "' created for feeddb");
}

print("User initialization completed successfully");
