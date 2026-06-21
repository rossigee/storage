FS Attachment migration in batches
==================================

This addon overrides the `force_storage` method to work only on the selected set
of records. This allows me (and you maybe) to import the data in batches, or in a
particular order etc.

Essentially this was written to work around the issue whereby the function
runs happily for 120 seconds, moving data from filestore to object store, then
the worker thread times out without committing the database transaction.
