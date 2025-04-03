"""added requests

Revision ID: 9c390b130e8d
Revises: c8c3fa638df3
Create Date: 2025-04-03 08:43:32.514648

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c390b130e8d'
down_revision = 'c8c3fa638df3'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('requests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('req_size', sa.String(length=100), nullable=True),
    sa.Column('status', sa.Boolean(), nullable=False),
    sa.Column('remarks', sa.String(), nullable=True),
    sa.Column('marked_read', sa.Boolean(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('requests')
    # ### end Alembic commands ###
