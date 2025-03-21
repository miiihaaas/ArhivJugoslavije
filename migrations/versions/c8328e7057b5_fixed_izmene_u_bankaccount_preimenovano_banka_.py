"""Izmene u BankAccount: preimenovano banka u namena (fixed)

Revision ID: c8328e7057b5_fixed
Revises: 1b00ef4fbbcd
Create Date: 2025-03-22 11:32:51.141755

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session


# revision identifiers, used by Alembic.
revision = 'c8328e7057b5_fixed'
down_revision = '1b00ef4fbbcd'
branch_labels = None
depends_on = None


def upgrade():
    # Proveravamo da li postoji kolona korišćenjem inspekcije baze podataka
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [column['name'] for column in inspector.get_columns('bank_account')]
    
    # Dodajemo novu kolonu purpose ako već ne postoji
    if 'purpose' not in columns:
        with op.batch_alter_table('bank_account', schema=None) as batch_op:
            batch_op.add_column(sa.Column('purpose', sa.String(length=100), nullable=True))
        
        # Kopiramo vrednosti iz bank u purpose
        connection.execute(sa.text("UPDATE bank_account SET purpose = bank"))
    
    # Proveravamo kolone ponovo nakon potencijalnog dodavanja nove kolone
    columns = [column['name'] for column in inspector.get_columns('bank_account')]
    
    # Menjamo purpose da bude NOT NULL i brišemo bank kolonu
    if 'purpose' in columns and 'bank' in columns:
        with op.batch_alter_table('bank_account', schema=None) as batch_op:
            # Definišemo tip kolone zajedno sa nullable atributom
            batch_op.alter_column('purpose', 
                                existing_type=sa.String(length=100),
                                nullable=False)
            batch_op.drop_column('bank')


def downgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [column['name'] for column in inspector.get_columns('bank_account')]
    
    if 'bank' not in columns:
        with op.batch_alter_table('bank_account', schema=None) as batch_op:
            batch_op.add_column(sa.Column('bank', sa.VARCHAR(length=100), nullable=True))
        
        # Kopiramo vrednosti iz purpose u bank
        connection.execute(sa.text("UPDATE bank_account SET bank = purpose"))
    
    # Proveravamo kolone ponovo nakon potencijalnog dodavanja nove kolone
    columns = [column['name'] for column in inspector.get_columns('bank_account')]
    
    if 'bank' in columns and 'purpose' in columns:
        with op.batch_alter_table('bank_account', schema=None) as batch_op:
            # Definišemo tip kolone zajedno sa nullable atributom
            batch_op.alter_column('bank', 
                               existing_type=sa.VARCHAR(length=100),
                               nullable=False)
            batch_op.drop_column('purpose')
