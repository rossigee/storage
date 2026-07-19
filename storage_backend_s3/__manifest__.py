# Copyright 2017 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# Copyright 2019 Camptocamp SA (http://www.camptocamp.com).
# @author Simone Orsi <simone.orsi@camptocamp.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    "name": "Storage Backend S3",
    "summary": "Amazon S3 storage backend",
    "version": "17.0.1.0.0",
    "license": "LGPL-3",
    "author": "Akretion,Camptocamp,Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/storage",
    "depends": [
        "storage_backend",
    ],
    "external_dependencies": {
        "python": [
            "boto3",
        ],
    },
    "maintainers": ["sebastienbeau", "simon-orsi"],
}