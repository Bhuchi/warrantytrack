# Single-AZ. Multi-AZ is the production answer and is documented as such in the
# report, but it doubles the database bill and the project budget is THB 4,000
# for the whole semester. Flip db_multi_az for a real production deployment.
#
# Lives in the private subnets with no route off the VPC.

resource "aws_db_subnet_group" "main" {
  count      = var.use_container_database ? 0 : 1
  name       = "${var.name}-db"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_instance" "main" {
  count = var.use_container_database ? 0 : 1

  identifier     = "${var.name}-db"
  engine         = "postgres"
  engine_version = "17"
  instance_class = var.db_instance_class

  allocated_storage     = 20
  max_allocated_storage = 50
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = local.db_name
  username = local.db_user

  # Write-only, so the password never lands in state. Paired with the same
  # ephemeral value written to SSM in secrets.tf.
  password_wo         = ephemeral.random_password.db.result
  password_wo_version = var.secret_version

  db_subnet_group_name   = aws_db_subnet_group.main[0].name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible    = false
  multi_az               = var.db_multi_az

  # Backups protect a running database. No final snapshot: the cost rules
  # call for tearing the stack down between sessions, and a named snapshot
  # makes the second teardown fail because the name is already taken.
  backup_retention_period = 7
  skip_final_snapshot     = true
  deletion_protection     = false

  auto_minor_version_upgrade = true
}
