"""init

Revision ID: 6b1a1474cfbb
Revises: 
Create Date: 2025-04-10 05:36:32.592847

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6b1a1474cfbb'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=100), nullable=True),
    sa.Column('email', sa.String(length=100), nullable=True),
    sa.Column('password', sa.String(length=300), nullable=True),
    sa.Column('isActive', sa.Boolean(), nullable=False),
    sa.Column('isAdmin', sa.Boolean(), nullable=False),
    sa.Column('superuser_id', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('requests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('req_size', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('remarks', sa.String(), nullable=True),
    sa.Column('marked_read', sa.Boolean(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('superuser_id', sa.Integer(), nullable=False),
    sa.Column('requested_on', sa.DateTime(), nullable=False),
    sa.Column('approved_size', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('user_config',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('folder_name', sa.String(length=100), nullable=True),
    sa.Column('max_size', sa.Integer(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('storage_upgraded', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('user_config')
    op.drop_table('requests')
    op.drop_table('users')
    # ### end Alembic commands ###
