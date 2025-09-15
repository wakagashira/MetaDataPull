IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='SalesforceFields' AND xtype='U')
CREATE TABLE SalesforceFields (
    ObjectName NVARCHAR(255),
    FieldName NVARCHAR(255),
    FieldLabel NVARCHAR(255),
    DataType NVARCHAR(255),
    LastSeen DATETIME NOT NULL,
    IsDeleted BIT NOT NULL DEFAULT 0,
    PRIMARY KEY (ObjectName, FieldName)
);
