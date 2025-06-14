// Switch to admin database to create user
db = db.getSiblingDB('admin');

// Create the root user if it doesn't exist
if (db.getUser("quaintly") == null) {
    db.createUser({
        user: "quaintly",
        pwd: "79_asVq0b4>Q",
        roles: [
            { role: "userAdminAnyDatabase", db: "admin" },
            { role: "readWriteAnyDatabase", db: "admin" },
            { role: "dbAdminAnyDatabase", db: "admin" }
        ]
    });
    print("Root user 'quaintly' created successfully");
}

// Switch to feeddb database
db = db.getSiblingDB('feeddb');

// Create application user for feeddb if it doesn't exist
if (db.getUser("quaintly") == null) {
    db.createUser({
        user: "quaintly",
        pwd: "79_asVq0b4>Q",
        roles: [
            { role: "readWrite", db: "feeddb" },
            { role: "dbAdmin", db: "feeddb" }
        ]
    });
    print("Database user 'quaintly' created for feeddb");
}

print("User initialization completed successfully");
